# Voice Agent Developer Guide

The `voice-agent` orchestrates the WebRTC connection, transcription, Large Language Model context injection, and fast local TTS synthesis.

## Environment Architecture

Because this relies extensively on heavy Python C-bindings (PyTorch, Numpy), we utilize `conda` to prevent package collision and linker issues across Apple Silicon and Windows environments securely.

### Quick Start
1. Ensure Miniconda is installed.
2. Inside the root of the project, generate the environment map:
   ```bash
   cd voice-agent
   conda env create -f environment.yml
   ```
   *(macOS users should use `environment-macos.yml`)*
3. Activate the fresh environment:
   ```bash
   conda activate aura
   ```
4. Start the script independently:
   ```bash
   python agent.py dev
   ```

## Running Automated Tests

When contributing PRs that touch the WebRTC socket logic or the Text-to-Speech logic, you **must** validate your changes against the Pytest harness.

We have a robust mocked framework located in `voice-agent/tests/`.

To execute:
```bash
cd voice-agent
conda activate aura
pip install pytest pytest-asyncio
pytest tests/
```
Ensure all tests evaluate to green before committing. 

## Editing the TTS
We use a wrapper around `Faster-Qwen3-TTS` located inside `aura_tts.py`.
Most parameter modifications (such as voice speed, pitch modulations, or strict memory pruning logic) will happen here. 
If you encounter memory leaks during synthesis generation, ensure you haven't dropped the `_gen_lock` thread-state which forces generation to be strictly synchronous on the GPU vector.
