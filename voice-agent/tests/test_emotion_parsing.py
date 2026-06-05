import sys
import os
import pytest

# Add parent to path to import vtube_controller
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from vtube_controller import VTUBE

def test_detect_emotion_single():
    text = "[happy] Hello there!"
    emotions = VTUBE.detect_emotion(text)
    assert "happy" in emotions
    assert len(emotions) == 1

def test_detect_emotion_multiple():
    text = "[smile, wink] I'm so glad to see you!"
    emotions = VTUBE.detect_emotion(text)
    assert "smile" in emotions
    assert "wink" in emotions

def test_format_for_tts_strips_tags():
    text = "[angry, shadow] I'm not happy about this."
    clean_text = VTUBE.format_for_tts(text)
    assert "[angry, shadow]" not in clean_text
    assert "I'm not happy about this." in clean_text

def test_format_for_tts_preserves_punctuation():
    text = "[happy] Hello! How are you?"
    clean_text = VTUBE.format_for_tts(text)
    assert clean_text == "Hello! How are you?"

def test_detect_emotion_case_insensitive():
    text = "[HAPPY] I am shouting!"
    emotions = VTUBE.detect_emotion(text)
    assert "happy" in emotions

def _strip_tags_like_process_input(chunks: list[str]) -> str:
    """Mirrors the per-character tag-stripping loop in _AuraSynthesizeStream._process_input."""
    in_tag = False
    tag_acc = ""
    result = ""
    for data in chunks:
        for ch in data:
            if ch == '[' and not in_tag:
                in_tag = True
                tag_acc = ch
            elif in_tag:
                tag_acc += ch
                if ch == ']':
                    in_tag = False
                    tag_acc = ""
            else:
                result += ch
    return result


def test_process_input_strips_complete_tag():
    out = _strip_tags_like_process_input(["[happy] Hello!"])
    assert "[" not in out and "]" not in out
    assert "Hello!" in out

def test_process_input_strips_tag_split_across_chunks():
    # Tag arrives in two SSE chunks — the bracket state must persist
    out = _strip_tags_like_process_input(["[smile, sad", "] World!"])
    assert "[" not in out and "]" not in out
    assert "World!" in out

def test_process_input_no_false_split_on_punctuation_inside_tag():
    # Malformed tag with '!' inside — must not bleed into clean text
    out = _strip_tags_like_process_input(["[smile, sad, finally show up!] Hey!"])
    assert "[" not in out and "]" not in out
    assert "Hey!" in out
    assert "show up" not in out   # tag content must be fully stripped

def test_process_input_multi_tag_sentence():
    chunks = ["[happy] Ray! ", "[sad, smile] I missed you!"]
    out = _strip_tags_like_process_input(chunks)
    assert "Ray!" in out
    assert "I missed you!" in out
    assert "[" not in out

def test_process_input_preserves_plain_text():
    out = _strip_tags_like_process_input(["Hello, how are you?"])
    assert out == "Hello, how are you?"


def test_format_for_tts_preserves_emphasis_tags():
    text = "Or wait... did you finally run out of content in *Neverness to Everness*?"
    clean_text = VTUBE.format_for_tts(text)
    assert "Neverness to Everness" in clean_text
    assert "*" not in clean_text


if __name__ == "__main__":
    # Manual run if needed
    print("Testing single tag...")
    print(f"Emotions: {VTUBE.detect_emotion('[happy] hi')}")
    print("Testing multi tag...")
    print(f"Emotions: {VTUBE.detect_emotion('[smile, wink] hi')}")
    print("Testing TTS formatting...")
    print(f"Clean: {VTUBE.format_for_tts('[angry] GO AWAY')}")
