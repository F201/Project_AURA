#include "qwen3_tts.h"

#include <jni.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <memory>
#include <string>
#include <vector>

namespace {
constexpr int sample_rate = 24000;

struct Voice {
    qwen3_tts::Qwen3TTS engine;
    std::vector<float> speaker;
};

void io_error(JNIEnv *env, const std::string &message) {
    if (jclass type = env->FindClass("java/io/IOException")) {
        env->ThrowNew(type, message.c_str());
    }
}

std::string path_string(JNIEnv *env, jstring value) {
    const char *chars = env->GetStringUTFChars(value, nullptr);
    if (!chars) return {};
    std::string result(chars);
    env->ReleaseStringUTFChars(value, chars);
    return result;
}
}

extern "C" JNIEXPORT jlong JNICALL
Java_com_aura_mobile_NativeVoice_open(JNIEnv *env, jclass, jstring directory, jstring embedding) {
    setenv("GGML_CPU_REUSE_WORKERS", "1", 0);
    const auto models = path_string(env, directory);
    const auto speaker = path_string(env, embedding);
    if (env->ExceptionCheck()) return 0;
    auto voice = std::make_unique<Voice>();
    if (!qwen3_tts::load_speaker_embedding_file(speaker, voice->speaker) || voice->speaker.size() != 1024) {
        io_error(env, "AURA's speaker embedding could not be loaded.");
        return 0;
    }
    if (!voice->engine.load_models(models, "qwen-talker-0.6b-base-Q4_K_M.gguf",
        models + "/qwen-tokenizer-12hz-Q8_0.gguf")) {
        io_error(env, voice->engine.get_error());
        return 0;
    }
    return reinterpret_cast<jlong>(voice.release());
}

extern "C" JNIEXPORT jshortArray JNICALL
Java_com_aura_mobile_NativeVoice_render(JNIEnv *env, jclass, jlong handle, jbyteArray utf8,
                                       jint language_id, jobject cancellation, jlongArray measurements,
                                       jint threads, jlong seed, jint chunk_millis) {
    auto &voice = *reinterpret_cast<Voice *>(handle);
    std::string text(env->GetArrayLength(utf8), '\0');
    env->GetByteArrayRegion(utf8, 0, static_cast<jsize>(text.size()), reinterpret_cast<jbyte *>(text.data()));
    jclass type = env->GetObjectClass(cancellation);
    jmethodID is_canceled = env->GetMethodID(type, "isCanceled", "()Z");
    env->DeleteLocalRef(type);
    if (env->ExceptionCheck()) return nullptr;
    auto canceled = [&] { return env->CallBooleanMethod(cancellation, is_canceled) == JNI_TRUE; };
    if (canceled()) return nullptr;

    qwen3_tts::tts_streaming_params options;
    options.chunk_sec = std::clamp<int32_t>(chunk_millis, 80, 2000) / 1000.0f;
    options.generation.max_audio_tokens = 384;
    options.generation.n_threads = std::clamp<int32_t>(threads, 1, 8);
    options.generation.seed = seed;
    options.generation.language_id = language_id;
    options.generation.repetition_penalty = 1.15f;
    options.generation.print_timing = false;
    std::vector<jshort> pcm;
    using clock = std::chrono::steady_clock;
    const auto start = clock::now();
    auto first_audio = start;
    auto milliseconds = [&](clock::time_point time) {
        return std::chrono::duration_cast<std::chrono::milliseconds>(time - start).count();
    };
    jlong no_gap_start = 0;
    int64_t frames = 0;
    const auto result = voice.engine.synthesize_with_speaker_embedding_streaming(text, voice.speaker,
        [&](const qwen3_tts::tts_audio_chunk &chunk) {
            if (canceled() || chunk.sample_rate != sample_rate) return false;
            const auto arrived = clock::now();
            if (pcm.empty()) first_audio = arrived;
            const jlong buffered_ms = static_cast<jlong>(pcm.size()) * 1000 / sample_rate;
            no_gap_start = std::max<jlong>(no_gap_start, milliseconds(arrived) - buffered_ms);
            frames += chunk.n_samples;
            for (int i = 0; i < chunk.n_samples; ++i) {
                const float value = chunk.samples[i];
                pcm.push_back(std::isfinite(value)
                    ? static_cast<jshort>(std::clamp(value, -1.0f, 1.0f) * 32767.0f)
                    : jshort{0});
            }
            return true;
        }, options);
    if (canceled()) return nullptr;
    if (!result.success || pcm.empty()) {
        io_error(env, result.error_msg.empty() ? "AURA did not generate audio." : result.error_msg);
        return nullptr;
    }
    if (measurements) {
        const jlong timing[] = {milliseconds(first_audio), milliseconds(clock::now()), no_gap_start, frames};
        const jsize count = std::min<jsize>(env->GetArrayLength(measurements), 4);
        env->SetLongArrayRegion(measurements, 0, count, timing);
    }
    auto samples = env->NewShortArray(static_cast<jsize>(pcm.size()));
    if (samples) env->SetShortArrayRegion(samples, 0, static_cast<jsize>(pcm.size()), pcm.data());
    return samples;
}

extern "C" JNIEXPORT void JNICALL
Java_com_aura_mobile_NativeVoice_close(JNIEnv *, jclass, jlong handle) {
    delete reinterpret_cast<Voice *>(handle);
}
