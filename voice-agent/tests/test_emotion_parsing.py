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
    text = "[smile, wink, blush] I'm so glad to see you!"
    emotions = VTUBE.detect_emotion(text)
    assert "smile" in emotions
    assert "wink" in emotions
    assert "blush" in emotions

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

if __name__ == "__main__":
    # Manual run if needed
    print("Testing single tag...")
    print(f"Emotions: {VTUBE.detect_emotion('[happy] hi')}")
    print("Testing multi tag...")
    print(f"Emotions: {VTUBE.detect_emotion('[smile, wink] hi')}")
    print("Testing TTS formatting...")
    print(f"Clean: {VTUBE.format_for_tts('[angry] GO AWAY')}")
