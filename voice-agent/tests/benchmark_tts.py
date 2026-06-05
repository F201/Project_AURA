import os
import time
import torch
import numpy as np
import soundfile as sf
import sys

# Add local lib to path
# Script is in voice-agent/tests/, so BASE_DIR should be voice-agent/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "lib", "faster-qwen3-tts"))

from faster_qwen3_tts.model import FasterQwen3TTS

def benchmark():
    model_name = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    ref_prompt_path = os.path.join(BASE_DIR, 'resources', 'voice', 'aura_voice_xvec.pt')
    
    print(f"Loading model: {model_name}...")
    t0 = time.perf_counter()
    model = FasterQwen3TTS.from_pretrained(
        model_name,
        device='cuda',
        dtype=torch.bfloat16,
        attn_implementation='eager',
        max_seq_len=512,
    )
    print(f"Model loaded in {time.perf_counter() - t0:.2f}s")
    
    print("Warming up...")
    model._warmup(64)
    
    text = "Hello! I am AURA, your personal AI assistant. I am happy to help you today! Ehehe!"
    
    print(f"\nBenchmarking non-streaming (baseline):")
    # Warmup 1 run
    model.generate_voice_clone(
        text=text,
        language="English",
        ref_audio=ref_prompt_path,
        ref_text="",
        max_new_tokens=256
    )
    
    runs = 5
    latencies = []
    for i in range(runs):
        torch.cuda.synchronize()
        start = time.perf_counter()
        audio, sr = model.generate_voice_clone(
            text=text,
            language="English",
            ref_audio=ref_prompt_path,
            ref_text="",
            max_new_tokens=256
        )
        torch.cuda.synchronize()
        latency = time.perf_counter() - start
        latencies.append(latency)
        print(f"  Run {i+1}: {latency:.3f}s")
        
    print(f"Average non-streaming latency: {np.mean(latencies):.3f}s")
    
    print(f"\nBenchmarking streaming (TTFA):")
    ttfas = []
    chunk_size = 8
    for i in range(runs):
        torch.cuda.synchronize()
        start = time.perf_counter()
        gen = model.generate_voice_clone_streaming(
            text=text,
            language="English",
            ref_audio=ref_prompt_path,
            ref_text="",
            chunk_size=chunk_size,
            max_new_tokens=256
        )
        first_chunk, sr, timing = next(gen)
        torch.cuda.synchronize()
        ttfa = time.perf_counter() - start
        ttfas.append(ttfa)
        print(f"  Run {i+1}: TTFA={ttfa:.3f}s")
        gen.close()
        
    print(f"Average streaming TTFA: {np.mean(ttfas):.3f}s")

    # Save a full sample from streaming for quality review
    print("\nGenerating quality sample from streaming...")
    torch.cuda.synchronize()
    gen = model.generate_voice_clone_streaming(
        text="This is a quality verification test for the optimized AURA streaming workflow. TTFA is significantly reduced while maintaining high acoustic fidelity. Ehehe!",
        language="English",
        ref_audio=ref_prompt_path,
        ref_text="",
        chunk_size=8,
        max_new_tokens=512
    )
    all_chunks = []
    for audio_chunk, sr, _timing in gen:
        all_chunks.append(audio_chunk)
    
    if all_chunks:
        full_audio = np.concatenate(all_chunks)
        out_path = os.path.join(BASE_DIR, "tests", "streaming_sample.wav")
        sf.write(out_path, full_audio, sr)
        print(f"Sample saved to: {out_path}")

if __name__ == "__main__":
    benchmark()
