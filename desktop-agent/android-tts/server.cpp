#include "httplib.h"
#include "qwen3_tts.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <mutex>
#include <vector>

int main(int argc, char **argv) {
    if (argc != 5) {
        std::fprintf(stderr, "Usage: aura-phone-tts MODEL_DIR TALKER_FILE CODEC_PATH SPEAKER_JSON\n");
        return 2;
    }

    std::vector<float> speaker;
    if (!qwen3_tts::load_speaker_embedding_file(argv[4], speaker) || speaker.size() != 1024) {
        std::fprintf(stderr, "Expected a 1024-value AURA speaker embedding\n");
        return 2;
    }

#if defined(__ANDROID__)
    setenv("GGML_CPU_REUSE_WORKERS", "1", 0);
#endif
    qwen3_tts::Qwen3TTS tts;
    if (!tts.load_models(argv[1], argv[2], argv[3])) {
        std::fprintf(stderr, "%s\n", tts.get_error().c_str());
        return 1;
    }

    constexpr int sample_rate = 24000;
    std::mutex generation;
    httplib::Server server;
    server.set_payload_max_length(4096);
    server.Get("/health", [](const httplib::Request &, httplib::Response &response) {
        response.set_content("ok", "text/plain");
    });
    server.Post("/speech", [&](const httplib::Request &request, httplib::Response &response) {
        if (request.body.find_first_not_of(" \t\r\n") == std::string::npos) {
            response.status = 400;
            return;
        }

        const auto language = request.get_header_value("X-TTS-Language");
        response.set_header("X-Sample-Rate", std::to_string(sample_rate));
        response.set_chunked_content_provider("application/octet-stream",
            [&, text = request.body, language](size_t, httplib::DataSink &sink) {
                std::lock_guard<std::mutex> lock(generation);
                if (!sink.is_writable()) {
                    return false;
                }

                qwen3_tts::tts_streaming_params options;
                // Two codec frames enable stateful vocoding without re-decoding the previous chunk.
                options.chunk_sec = 0.16f;
                options.generation.max_audio_tokens = 384;
                options.generation.n_threads = 4;
                options.generation.language_id = language == "ja" ? 2058 : 2050;
                options.generation.repetition_penalty = 1.15f;
                options.generation.print_timing = false;

                bool sent_audio = false;
                const auto result = tts.synthesize_with_speaker_embedding_streaming(text, speaker,
                    [&](const qwen3_tts::tts_audio_chunk &chunk) {
                        if (chunk.sample_rate != sample_rate || !sink.is_writable()) {
                            return false;
                        }
                        std::vector<int16_t> pcm(chunk.n_samples);
                        std::transform(chunk.samples, chunk.samples + chunk.n_samples, pcm.begin(), [](float sample) {
                            return std::isfinite(sample)
                                ? static_cast<int16_t>(std::clamp(sample, -1.0f, 1.0f) * 32767.0f)
                                : int16_t{0};
                        });
                        if (pcm.empty()) {
                            return true;
                        }
                        sent_audio = sink.write(reinterpret_cast<const char *>(pcm.data()), pcm.size() * sizeof(int16_t));
                        return sent_audio;
                    }, options);

                if (!result.success || !sent_audio) {
                    std::fprintf(stderr, "Phone TTS request ended without a complete stream: %s\n", result.error_msg.c_str());
                    return false;
                }
                sink.done();
                return true;
            });
    });

    constexpr int port = 17865;
    if (!server.bind_to_port("127.0.0.1", port)) {
        std::fprintf(stderr, "Could not bind phone TTS to 127.0.0.1:%d\n", port);
        return 1;
    }
    std::fprintf(stderr, "AURA phone TTS ready on 127.0.0.1:%d\n", port);
    return server.listen_after_bind() ? 0 : 1;
}
