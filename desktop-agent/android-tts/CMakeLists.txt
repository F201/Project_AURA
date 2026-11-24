cmake_minimum_required(VERSION 3.24)
project(aura_phone_tts LANGUAGES C CXX)

set(QWEN3_TTS_DIR "" CACHE PATH "Path to the pinned qwen3-tts.cpp source tree")
add_subdirectory("${QWEN3_TTS_DIR}" qwen3-tts EXCLUDE_FROM_ALL)

file(DOWNLOAD
    https://raw.githubusercontent.com/yhirose/cpp-httplib/v0.67.0/httplib.h
    "${CMAKE_CURRENT_BINARY_DIR}/include/httplib.h"
    EXPECTED_HASH SHA256=3ec770608b295d12bf7bb6cca47f4b8249f6e15261e2587ba0b288f4bfc397ce
    TLS_VERIFY ON)

add_executable(aura-phone-tts server.cpp)
target_compile_features(aura-phone-tts PRIVATE cxx_std_17)
target_include_directories(aura-phone-tts PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/include")
target_compile_definitions(aura-phone-tts PRIVATE CPPHTTPLIB_THREAD_POOL_COUNT=4)
target_link_libraries(aura-phone-tts PRIVATE qwen3_tts)
