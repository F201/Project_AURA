package com.aura.mobile;

import android.os.Build;
import android.os.CancellationSignal;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

final class NativeVoice implements AutoCloseable {
    static final int SAMPLE_RATE = 24_000;
    static final int PREFERRED_THREADS = "a56x".equals(Build.DEVICE) ? 6 : 4;
    static final int CHUNK_MILLIS = 160;
    private long handle;

    NativeVoice(VoiceModels models) throws IOException {
        System.loadLibrary("aura_voice");
        handle = open(models.directory.getAbsolutePath(), models.embedding().getAbsolutePath());
        if (handle == 0) throw new IOException("The voice model could not be loaded.");
    }

    short[] generate(String text, CancellationSignal cancellation) throws IOException {
        return generate(text, cancellation, null, PREFERRED_THREADS, -1, CHUNK_MILLIS);
    }

    short[] generate(String text, CancellationSignal cancellation, long[] measurements,
                     int threads, long seed, int chunkMillis) throws IOException {
        if (handle == 0) throw new IOException("The voice model is closed.");
        boolean japanese = text.codePoints().anyMatch(codepoint -> {
            Character.UnicodeScript script = Character.UnicodeScript.of(codepoint);
            return script == Character.UnicodeScript.HIRAGANA || script == Character.UnicodeScript.KATAKANA;
        });
        return render(handle, text.getBytes(StandardCharsets.UTF_8), japanese ? 2058 : 2050,
            cancellation, measurements, threads, seed, chunkMillis);
    }

    @Override public void close() {
        if (handle != 0) close(handle);
        handle = 0;
    }

    private static native long open(String directory, String embedding) throws IOException;
    private static native short[] render(long handle, byte[] text, int languageId, CancellationSignal cancellation,
                                        long[] measurements, int threads, long seed, int chunkMillis) throws IOException;
    private static native void close(long handle);
}
