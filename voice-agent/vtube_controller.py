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
        self.is_enabled = os.getenv("VTUBE_ENABLED", "false").lower() == "true"
        self._connected_loop = None  # Track which event loop owns the VTS connection
        
        if not self.is_enabled:
            logger.info("VTube Studio integration is DISABLED via .env")
            return
        
        # Expression mapping (matches hotkey names or filenames in VTube Studio)
        self.expressions = {
            "happy": "Smile",
            "sad": "Sad",
            "smile": "Smile",
            "angry": "Angry",
            "ghost": "Ghost Happy",
            "ghost_nervous": "Ghost Nervous",
            "shadow": "Shadow",
            "eyeshine_off": "Eyeshine Off",
            "pupil_shrink": "Pupil Shrink",
            "neutral": None,
            # Japanese Aliases
            "喜び": "Smile",
            "嬉しい": "Smile",
            "悲しい": "Sad",
            "怒り": "Angry",
            "笑顔": "Smile",
            "幽霊": "Ghost Happy",
            "緊張": "Ghost Nervous",
            "影": "Shadow",
            "瞳孔": "Pupil Shrink"
        }
        self.expression_hotkey_map = {}
        
        # Bilingual emotion keywords
        self.emotion_keywords = {
            
            "happy": [
                # English
                "happy", "glad", "great", "awesome", "wonderful", "love", "like", 
                "enjoy", "fun", "yay", "excited", "joy", "cheerful", "delighted",
                # Japanese
                "嬉しい", "うれしい", "楽しい", "たのしい", "幸せ", "しあわせ",
                "やった", "最高", "さいこう", "素晴らしい", "すばらしい", "ワクワク"
            ],
            "sad": [
                # English
                "sad", "sorry", "unfortunate", "regret", "miss", "lonely", "cry", 
                "depressed", "upset", "unhappy", "miserable", "heartbroken",
                # Japanese
                "悲しい", "かなしい", "寂しい", "さびしい", "辛い", "つらい",
                "残念", "ざんねん", "泣", "ない", "切ない", "せつない"
            ],
            "angry": [
                # English
                "angry", "mad", "annoyed", "frustrated", "hate", "stupid", "idiot", 
                "dumb", "terrible", "furious", "irritated", "pissed",
                # Japanese
                "怒", "おこ", "怒る", "おこる", "イライラ", "いらいら", "腹立つ",
                "はらだつ", "馬鹿", "ばか", "嫌い", "きらい", "最悪", "さいあく",
                "もう！", "信じられない"
            ],
            "smile": [
                # English
                "smile", "grin", "chuckle", "giggle", "teehee", "hehe", "haha",
                # Japanese
                "笑", "わら", "微笑む", "ほほえむ", "ニヤニヤ", "にやにや", "くすくす",
                "あはは", "ふふふ"
            ],
            "ghost": [
                # English
                "ghost", "boo", "spooky", "scared", "afraid", "spirit", "haunted", "dead",
                # Japanese
                "幽霊", "ゆうれい", "お化け", "おばけ", "怖い", "こわい", "霊", "れい"
            ],
            "ghost_nervous": ["nervous", "flustered", "caught", "embarrassed", "shook"],
            "shadow": ["scary", "menacing", "dark", "evil", "shadow", "creepy"],
            "eyeshine_off": ["deadface", "disappointed", "uncool", "serious", "cold", "empty"],
            "pupil_shrink": ["prank", "mischief", "cheeky", "teasing", "silly", "surprise"]
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

    async def set_expression(self, expression_names, reset_after=None):
        """Set one or more expressions by name. 
        Enforces mutual exclusivity for base emotions (happy, sad, etc.)."""
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
            
        # Enforce base emotion rules:
        # 1. Base emotions are generally mutually exclusive.
        # 2. EXCEPTION: [angry, sad] is allowed for a 'pleading/memelas' look (order matters).
        final_expressions = []
        base_emotions_found = []
        
        for name in expression_names:
            if name in self.BASE_EMOTIONS:
                # Special case: allow 'sad' if 'angry' was already added
                if name == "sad" and "angry" in base_emotions_found and "sad" not in base_emotions_found:
                    final_expressions.append(name)
                    base_emotions_found.append(name)
                elif not base_emotions_found:
                    final_expressions.append(name)
                    base_emotions_found.append(name)
                else:
                    logger.debug(f"Skipping exclusive base emotion: {name}")
            else:
                final_expressions.append(name)

        for expression_name in final_expressions:
            hotkey_id = self.expression_hotkey_map.get(expression_name)
            if not hotkey_id:
                logger.debug(f"No hotkey ID found for expression: {expression_name}")
                continue
            
            try:
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
                        return

                logger.info(f"Triggered expression: {expression_name} (ID: {hotkey_id})")
            except Exception as e:
                logger.error(f"Failed to trigger expression {expression_name}: {e}")
                self.connected = False
    
    def detect_emotion(self, text):
        """Bilingual detection: Looks for explicit tags [tag1, tag2] first, then falls back to keywords."""
        if not self.is_enabled:
            return []
            
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
            "tilts head", "winks", "shrugs", "sighs", "giggles"
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