"""Convert AURA's checked-in Qwen3-TTS voice prompt to a speaker embedding JSON array."""

import argparse
import json
from pathlib import Path

import torch


class VoiceClonePromptItem:
    """Load the saved fields without importing the Qwen3-TTS runtime."""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    prompt_type = (VoiceClonePromptItem, "qwen_tts.inference.qwen3_tts_model.VoiceClonePromptItem")
    with torch.serialization.safe_globals([prompt_type]):
        prompts = torch.load(args.prompt, map_location="cpu", weights_only=True)
    embedding = prompts[0].ref_spk_embedding.detach().float()
    if embedding.shape != (1024,) or not torch.isfinite(embedding).all():
        raise ValueError("Expected 1024 finite speaker embedding values for Qwen3-TTS 0.6B")
    args.output.write_text(json.dumps(embedding.tolist()) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
