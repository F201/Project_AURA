"""
VTube Studio Controller — Trigger VTube expressions via API
Bilingual: English + Japanese emotion detection
"""
import asyncio
import pyvts
import logging
import re
import os

logger = logging.getLogger("vtube_controller")

class VTubeController:
    def __init__(self):
        # Use absolute path for token.txt to avoid CWD issues
        base_dir = os.path.dirname(os.path.abspath(__file__))
        token_path = os.path.join(base_dir, "token.txt")
        
        self.plugin_info = {
            "plugin_name": "AURA-Agent",
            "developer": "Raygama",
            "authentication_token_path": token_path
        }
        self.vts = None
        self.connected = False
        self.is_enabled = os.getenv("VTUBE_ENABLED", "false").lower() == "true"
        self._connected_loop = None  # Track which event loop owns the VTS connection
        self._vts_lock = asyncio.Lock()  # Serialize all VTS API requests
        self.active_expressions = {}  # name -> hotkey_id, tracks which expressions are currently active

        # Always initialized — detect_emotion() uses these regardless of VTube being enabled
        self.expressions = {
            "sad": "Sad",
            "smile": "Smile",
            "angry": "Angry",
            "ghost": "Ghost Happy",
            "ghost_nervous": "Ghost Nervous",
            "shadow": "Shadow",
            "eyeshine_off": "Eyeshine Off",
            "pupil_shrink": "Pupil Shrink",
            "neutral": None,
            "喜び": "Smile",
            "嬉しい": "Smile",
            "悲しい": "Sad",
            "怒り": "Angry",
            "笑顔": "Smile",
            "幽霊": "Ghost Happy",
            "緊張": "Ghost Nervous",
            "影": "Shadow",
            "瞳孔": "Pupil Shrink",
            "wink": "EyeOpenLeft",
            "tongue": "TongueOut",
            "ウインク": "wink",
            "べー": "tongue"
        }

        self.emotion_keywords = {
            "sad": [
                # English
                "sad", "sadly", "sorry", "unfortunate", "regret", "miss", "lonely", "cry", "crying",
                "depressed", "depressing", "upset", "unhappy", "miserable", "heartbroken",
                # Japanese
                "悲しい", "かなしい", "寂しい", "さびしい", "辛い", "つらい",
                "残念", "ざんねん", "泣", "ない", "切ない", "せつない"
            ],
            "angry": [
                # English
                "angry", "mad", "annoyed", "annoying", "frustrated", "frustrating", "hate", "hated", "stupid", "idiot", 
                "dumb", "terrible", "furious", "irritated", "irritating", "pissed",
                # Japanese
                "怒", "おこ", "怒る", "おこる", "イライラ", "いらいら", "腹立つ",
                "はらだつ", "馬鹿", "ばか", "嫌い", "きらい", "最悪", "さいあく",
                "もう！", "信じられない"
            ],
            "smile": [
                # English
                "smile", "smiling", "grin", "grinning", "chuckle", "chuckling", "giggle", "giggling", "teehee", "hehe", "haha",
                "happy", "glad", "great", "awesome", "wonderful", "love", "like", 
                "enjoy", "fun", "yay", "excited", "exciting", "joy", "cheerful", "delighted",
                # Japanese
                "笑", "わら", "微笑む", "ほほえむ", "ニヤニヤ", "にやにや", "くすくす",
                "あはは", "ふふふ",
                "嬉しい", "うれしい", "楽しい", "たのしい", "幸せ", "しあわせ",
                "やった", "最高", "さいこう", "素晴らしい", "すばらしい", "ワクワク"
            ],
            "ghost": [
                # English
                "ghost", "boo", "spooky", "scared", "scary", "afraid", "spirit", "haunted", "dead",
                # Japanese
                "幽霊", "ゆうれい", "お化け", "おばけ", "怖い", "こわい", "霊", "れい"
            ],
            "ghost_nervous": ["nervous", "flustered", "caught", "embarrassed", "embarrassing", "shook", "shocked"],
            "shadow": ["scary", "menacing", "dark", "evil", "shadow", "creepy"],
            "eyeshine_off": ["deadface", "disappointed", "uncool", "serious", "cold", "empty"],
            "pupil_shrink": ["prank", "mischief", "cheeky", "teasing", "silly", "surprise", "surprised"],
            "wink": ["wink", "blink", "winked", "winking", "ウインク"],
            "tongue": ["tongue", "bleh", "cheeky", "sticking out", "べー"]
        }

        if not self.is_enabled:
            logger.info("VTube Studio integration is DISABLED via .env")
            return

        self.expression_hotkey_map = {}
        self.injected_parameters = {}
        self.turn_animation_log = set()
        self.PARAM_TO_FEATURE = {
            "EyeOpenLeft": "wink",
            "EyeOpenRight": "wink",
            "BrowLeftY": "wink",
            "MouthSmile": "wink",
            "TongueOut": "tongue",
            "MouthOpen": "tongue"
        }

    async def connect(self):
        """Connect to VTube Studio with robust re-authentication."""
        if not self.is_enabled:
            return False
            
        current_loop = asyncio.get_event_loop()
        
        # If we're on a different event loop, force reconnect (LiveKit forks new processes)
        if self.connected and self.vts and self._connected_loop is not None:
            if self._connected_loop != current_loop:
                logger.info("Event loop changed (new worker process). Forcing VTS reconnect...")
                self.connected = False
                self.vts = None
        
        if self.connected and self.vts:
            return True
            
        token_path = self.plugin_info.get("authentication_token_path", "./token.txt")
        
        try:
            # Explicitly set port and host to match user's VTS settings
            self.vts = pyvts.vts(plugin_info=self.plugin_info, host="127.0.0.1", port=8001)
            await self.vts.connect()
            
            # 1. Request token if not present or invalid
            await self.vts.request_authenticate_token()
            
            # 2. Authenticate
            auth_res = await self.vts.request_authenticate()
            
            # Check if auth_res is a dictionary and contains authentication data
            is_authenticated = False
            if isinstance(auth_res, dict):
                is_authenticated = auth_res.get("data", {}).get("authenticated", False)
            elif isinstance(auth_res, bool):
                is_authenticated = auth_res

            if not is_authenticated:
                logger.warning("VTube Studio authentication failed or revoked. Attempting token repair...")
                
                # Delete token file and try one more time
                if os.path.exists(token_path):
                    try:
                        os.remove(token_path)
                    except Exception as e:
                        logger.error(f"Could not delete token file: {e}")
                    
                # Retry once
                await self.vts.request_authenticate_token()
                auth_res = await self.vts.request_authenticate()
                
                final_auth = False
                if isinstance(auth_res, dict):
                    final_auth = auth_res.get("data", {}).get("authenticated", False)
                elif isinstance(auth_res, bool):
                    final_auth = auth_res

                if not final_auth:
                    logger.error("Final authentication attempt failed. Please ensure 'Enable API' is on in VTube Studio.")
                    self.connected = False
                    return False

            # 3. Fetch hotkeys only after successful authentication
            await self._cache_hotkeys()
            
            if not self.expression_hotkey_map:
                logger.warning("VTube Studio connected, but no hotkeys were found for the current model.")
            
            self.connected = True
            self._connected_loop = current_loop
            logger.info("Successfully connected to VTube Studio and cached hotkeys.")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to VTube Studio: {e}")
            self.connected = False
            return False
    
    async def _cache_hotkeys(self):
        """Fetch available hotkeys and map them to our internal expression names"""
        try:
            async with self._vts_lock:
                response = await self.vts.request({
                    "apiName": "VTubeStudioPublicAPI",
                    "apiVersion": "1.0",
                    "requestID": "cacheHotkeys",
                    "messageType": "HotkeysInCurrentModelRequest"
                })
            
            available_hotkeys = response.get("data", {}).get("availableHotkeys", [])
            
            # Reset mapping
            self.expression_hotkey_map = {}
            
            # Reverse mapping to find hotkey IDs by filename or name
            # Humans use expression names (happy, sad), we map them to VTS hotkey IDs
            for emotion, target_name in self.expressions.items():
                if target_name is None:
                    continue
                
                # Prioritize exact match on hotkey Name
                for hk in available_hotkeys:
                    hk_name = hk.get("name", "")
                    hk_file = hk.get("file", "")
                    
                    if target_name.lower() == hk_name.lower() or target_name.lower() in hk_file.lower():
                        self.expression_hotkey_map[emotion] = hk.get("hotkeyID")
                        logger.debug(f"Mapped {emotion} -> {hk.get('hotkeyID')} ({hk_name})")
                        break
            
            logger.info(f"Cached {len(self.expression_hotkey_map)} expressions")
            
        except Exception as e:
            logger.error(f"Failed to cache hotkeys: {e}")

    async def disconnect(self):
        """Disconnect from VTube Studio"""
        if self.vts:
            await self.vts.close()
            self.connected = False
            self.vts = None
            logger.info("Disconnected from VTube Studio")
    
    BASE_EMOTIONS = ["happy", "sad", "smile", "angry", "ghost", "ghost_nervous"]
    FEATURES = ["wink", "tongue"]
    AMPLIFIERS = ["shadow", "eyeshine_off", "pupil_shrink"]
    
    # Allowed multi-base combos (order-independent)
    ALLOWED_COMBOS = [
        {"angry", "sad"},      # Pleading / Girlfriend Mad
        {"sad", "smile"},      # Genuinely Worried / Uncertain Smile
        {"angry", "smile"},    # Devilish Grin
    ]

    async def start_turn(self):
        """Called at the start of a new interaction to reset turn-based logic."""
        self.turn_animation_log.clear()
        logger.debug("Turn animation log cleared.")

    async def set_expression(self, expression_names, reset_after=None):
        """Set one or more expressions by name.
        Allows specific multi-base combos and duplicate base emotions for nuance."""
        if not self.is_enabled:
            return
            
        if not self.connected or not self.vts:
            logger.info("VTube Studio not connected. Attempting to reconnect...")
            if not await self.connect():
                return
        
        # Double check cache if empty (safety net)
        if not self.expression_hotkey_map:
            await self._cache_hotkeys()
        
        if isinstance(expression_names, str):
            expression_names = [expression_names]
        
        # Pass through all expressions — the LLM is now trained on the correct recipes.
        # We just validate that base emotion combos are in our allowed list.
        base_in_request = [n for n in expression_names if n in self.BASE_EMOTIONS]
        unique_bases = set(base_in_request)
        
        # If there are multiple DIFFERENT base emotions, check they form an allowed combo
        if len(unique_bases) > 1:
            if unique_bases not in self.ALLOWED_COMBOS:
                # Not an allowed combo — keep only the first base emotion + amplifiers
                first_base = base_in_request[0]
                expression_names = [first_base] + [n for n in expression_names if n in self.AMPLIFIERS]
                logger.debug(f"Filtered disallowed combo to: {expression_names}")

        # target_sequence: list of (hotkey_id or None, expr_name)
        target_sequence = []  
        target_id_set = set() # Unique hotkeys intended to be active
        
        for expr in expression_names:
            hotkey_id = self.expression_hotkey_map.get(expr)
            # Add to sequence if it's a known emotion, even if no hotkey ID (for features)
            if expr in self.expressions:
                target_sequence.append((hotkey_id, expr))
                if hotkey_id:
                    target_id_set.add(hotkey_id)
        
        active_id_set = set(self.active_expressions.values())
        
        # 1. Turn OFF hotkeys that are active but NOT in the new target
        ids_to_off = active_id_set - target_id_set
        for hid in ids_to_off:
            # Find the name we used to activate this hotkey
            names = [n for n, h in self.active_expressions.items() if h == hid]
            if names:
                await self._trigger_hotkey(names[0])
                del self.active_expressions[names[0]]
            
        # 1.1 Turn OFF injected parameters if their controlling feature is not in target
        for p_name in list(self.injected_parameters.keys()):
            feature = self.PARAM_TO_FEATURE.get(p_name)
            if feature not in expression_names:
                # Reset to a safe default (usually 1.0 for eyes, 0.0 for tongue/mouth)
                default_val = 1.0 if "EyeOpen" in p_name else 0.0
                await self.inject_parameter(p_name, default_val)
                del self.injected_parameters[p_name]

        # 2. Sequential triggers for requested expressions (including duplicates)
        recent_features = set() # Prevent redundant injections in same call
        for hotkey_id, expr in target_sequence:
            # Prevent double-winking/tongue if already done this turn
            if expr in self.FEATURES and expr in self.turn_animation_log:
                continue

            if expr in self.active_expressions and self.active_expressions[expr] == hotkey_id:
                await self._trigger_hotkey(expr, hotkey_id, action="Toggled OFF to pulse")
                del self.active_expressions[expr]
                await asyncio.sleep(0.35) 
                
            success = await self._trigger_hotkey(expr, hotkey_id)
            if success:
                # Add to active tracking
                self.active_expressions[expr] = hotkey_id
            
            # Special handling for direct parameters (wink/tongue)
            if expr == "wink" and "wink" not in recent_features:
                # Natural Wink: Close left eye, lower left brow, smile more
                await self.inject_parameter("EyeOpenLeft", 0.0)
                await self.inject_parameter("BrowLeftY", 0.0) 
                await self.inject_parameter("MouthSmile", 1.0)
                self.injected_parameters["EyeOpenLeft"] = 0.0
                self.injected_parameters["BrowLeftY"] = 0.0
                self.injected_parameters["MouthSmile"] = 1.0
                recent_features.add("wink")
                self.turn_animation_log.add("wink")
            elif expr == "tongue" and "tongue" not in recent_features:
                # Stick tongue out (value 1.0) AND open mouth WIDE (value 1.0)
                # Most models need the mouth fully open to see the tongue!
                await self.inject_parameter("MouthOpen", 1.0)
                await self.inject_parameter("TongueOut", 1.0)
                await self.inject_parameter("MouthSmile", 0.0)
                self.injected_parameters["MouthOpen"] = 1.0
                self.injected_parameters["TongueOut"] = 1.0
                self.injected_parameters["MouthSmile"] = 0.0
                recent_features.add("tongue")
                self.turn_animation_log.add("tongue")
                
            await asyncio.sleep(0.35)

    async def inject_parameter(self, parameter_name, value):
        """Directly inject a numerical value into a Live2D parameter."""
        if not self.connected or not self.vts:
            return False
            
        try:
            async with self._vts_lock:
                await self.vts.request({
                    "apiName": "VTubeStudioPublicAPI",
                    "apiVersion": "1.0",
                    "requestID": f"inject_{parameter_name}",
                    "messageType": "InjectParameterDataRequest",
                    "data": {
                        "parameterValues": [
                            {
                                "id": parameter_name,
                                "value": float(value),
                                "weight": 1.0
                            }
                        ]
                    }
                })
            return True
        except Exception as e:
            logger.error(f"Failed to inject parameter {parameter_name}: {e}")
            return False

    async def _trigger_hotkey(self, expression_name, hotkey_id=None, action="Triggered"):
        hotkey_id = hotkey_id if hotkey_id else self.expression_hotkey_map.get(expression_name)
        if not hotkey_id:
            logger.debug(f"No hotkey ID found for expression: {expression_name}")
            return False
        
        try:
            async with self._vts_lock:
                response = await self.vts.request({
                    "apiName": "VTubeStudioPublicAPI",
                    "apiVersion": "1.0",
                    "requestID": f"trigger_{expression_name}",
                    "messageType": "HotkeyTriggerRequest",
                    "data": {
                        "hotkeyID": hotkey_id
                    }
                })
            
            if response.get("messageType") == "APIError":
                data = response.get("data", {})
                if data.get("errorID") in [100, 101]: # Authentication errors
                    logger.warning("VTube Studio authentication expired. Reconnecting...")
                    self.connected = False
                    return False
            logger.info(f"{action} expression: {expression_name} (ID: {hotkey_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to trigger expression {expression_name}: {e}")
            self.connected = False
            return False

    async def reset_to_neutral(self):
        """Reset face to neutral state: no active expressions, defaulting to base model."""
        if not self.is_enabled or not self.connected:
            return
        
        # Turn off all active expressions
        for expr_name in list(self.active_expressions.keys()):
            await self._trigger_hotkey(expr_name)
        self.active_expressions.clear()
    
    def detect_emotion(self, text):
        """Bilingual detection: Looks for explicit tags [tag1, tag2] first, then falls back to keywords."""
        text_lower = text.lower()
        
        # 1. Look for explicit tags in brackets [happy, pupil_shrink]
        tags = re.findall(r'\[([^\]]+)\]', text_lower)
        if tags:
            # Flatten comma-separated lists inside brackets: [happy, pupil_shrink] -> ['happy', 'pupil_shrink']
            found_tags = []
            for tag_group in tags:
                parts = [p.strip() for p in tag_group.split(',')]
                for p in parts:
                    if p in self.expressions:
                        found_tags.append(p)
            if found_tags:
                return found_tags
        
        # 2. Fallback to keyword matching
        for emotion, keywords in self.emotion_keywords.items():
            for kw in keywords:
                # Use word boundaries for English keywords
                if re.search(rf'\b{re.escape(kw.lower())}\b', text_lower):
                    return [emotion]
                # For Japanese
                if any('\u3040' <= char <= '\u30ff' or '\u4e00' <= char <= '\u9fff' for char in kw):
                    if kw in text:
                        return [emotion]
        
        return []
    
    def format_for_tts(self, text: str) -> str:
        """
        Clean LLM output for TTS:
        - Remove roleplay cues (*acting*, _thinking_, [action], cracks knuckles)
        - Remove emojis and kaomoji
        - Remove parenthetical stage directions
        - Remove URLs
        - Normalize whitespace
        """
        if not text:
            return ""
        
        # 1. Remove bracketed tags [happy, pupil_shrink] specifically
        text = re.sub(r'\[[^\]]+\]', '', text)
        
        # 2. Remove roleplay symbols (*acting*, _thinking_, (giggles))
        text = re.sub(r'[*_][^*_]+[*_]', '', text)
        text = re.sub(r'\([^)]+\)', '', text)
        
        # 2. Remove common roleplay "plain text" phrases the LLM might hallucinate
        roleplay_phrases = [
            "cracks knuckles", "huffs dramatically", "twirls playfully", 
            "tilts head", "winks", "shrugs", "sighs", "giggles",
            "EyeOpenLeft", "EyeOpenRight", "TongueOut",
            "MouthOpen", "Brows", "MouthX",
            "ウインク", "べー"
        ]
        for phrase in roleplay_phrases:
            text = re.sub(rf'\b{re.escape(phrase)}\b', '', text, flags=re.IGNORECASE)
            
        # 3. Remove URLs
        text = re.sub(r'http[s]?://\S+', '', text)
        
        # 4. Remove emojis (Unicode ranges)
        emoji_pattern = re.compile(
            "["
            "\U0001F000-\U0001F9FF"  # Modern emojis (Emoticons, Symbols, Transport, etc.)
            "\U0001FA00-\U0001FAFF"  # Extended symbols
            "\U00002600-\U000027BF"  # Miscellaneous symbols & Dingbats
            "]+", flags=re.UNICODE
        )
        text = emoji_pattern.sub('', text)
        
        # 5. Remove Japanese brackets 「」
        text = re.sub(r'[「」]', '', text)
        
        # 6. Final cleanup of any remaining markdown/formatting characters
        text = re.sub(r'[*_`#~]', '', text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text


# Global singleton
VTUBE = VTubeController()