package com.aura.mobile;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.AudioDeviceInfo;
import android.media.AudioFocusRequest;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.os.CancellationSignal;
import android.os.SystemClock;
import android.util.Log;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;
import java.util.regex.Pattern;

final class VoiceOutput implements AutoCloseable {
    record Playback(int framesPlayed, int underruns) {}
    private static final Pattern SENTENCES = Pattern.compile("(?<=[.!?。！？])\\s+|(?<=[。！？])|\\n+");
    private static final AudioAttributes AUDIO = new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();
    private final ExecutorService generator = Executors.newSingleThreadExecutor();
    private final ExecutorService player = Executors.newSingleThreadExecutor();
    private final VoiceModels models;
    private final Context context;
    private NativeVoice voice;

    VoiceOutput(Context context, VoiceModels models) {
        this.context = context.getApplicationContext();
        this.models = models;
    }

    void warm(Consumer<String> error) {
        generator.execute(() -> {
            try {
                ensureVoice();
            } catch (IOException | LinkageError failure) {
                error.accept(failure.getMessage());
            }
        });
    }

    Turn turn(CancellationSignal cancel, Consumer<Float> mouth, Consumer<String> speaking, Consumer<String> error, Runnable done) {
        return new Turn(cancel, mouth, speaking, error, done);
    }

    final class Turn {
        private final CancellationSignal cancel;
        private final Consumer<Float> mouth;
        private final Consumer<String> speaking;
        private final Consumer<String> error;
        private final Runnable done;
        private final StringBuilder pending = new StringBuilder();
        private final AtomicBoolean failed = new AtomicBoolean();
        private boolean sealed;

        Turn(CancellationSignal cancel, Consumer<Float> mouth, Consumer<String> speaking, Consumer<String> error, Runnable done) {
            this.cancel = cancel;
            this.mouth = mouth;
            this.speaking = speaking;
            this.error = error;
            this.done = done;
        }

        void feed(String delta) {
            if (sealed || cancel.isCanceled()) return;
            pending.append(delta);
            for (int cut; (cut = speechBoundary(pending)) > 0; ) {
                queue(clauses(pending.substring(0, cut)));
                pending.delete(0, cut);
            }
        }

        void finish() {
            if (sealed) return;
            sealed = true;
            if (!cancel.isCanceled()) queue(clauses(pending.toString()));
            pending.setLength(0);
            player.execute(done);
        }

        private void queue(List<String> chunks) {
            for (String clause : chunks) enqueue(clause);
        }

        private void enqueue(String clause) {
            CompletableFuture<short[]> audio = new CompletableFuture<>();
            generator.execute(() -> {
                try {
                    audio.complete(cancel.isCanceled() || failed.get() ? null : ensureVoice().generate(clause, cancel));
                } catch (IOException | RuntimeException | LinkageError failure) {
                    failed.set(true);
                    audio.completeExceptionally(failure);
                }
            });
            player.execute(() -> {
                try {
                    short[] pcm = audio.join();
                    if (pcm != null && !cancel.isCanceled() && !failed.get()) {
                        play(context, pcm, cancel, mouth, () -> speaking.accept(clause), () -> {});
                    }
                } catch (Exception failure) {
                    failed.set(true);
                    if (!cancel.isCanceled()) {
                        Throwable cause = failure.getCause();
                        error.accept((cause == null ? failure : cause).getMessage());
                    }
                } finally {
                    mouth.accept(0f);
                }
            });
        }
    }

    static int speechBoundary(CharSequence text) {
        var sentences = SENTENCES.matcher(text);
        while (sentences.find()) {
            if (sentences.end() >= 10) return sentences.end();
        }
        if (text.length() < 100) return 0;
        for (int i = Math.min(text.length() - 1, 144); i >= 40; i--) {
            char c = text.charAt(i);
            if (c == ',' || c == '、' || c == '—' || Character.isWhitespace(c)) return i + 1;
        }
        return 0;
    }

    private NativeVoice ensureVoice() throws IOException {
        if (voice == null) voice = new NativeVoice(models);
        return voice;
    }

    static List<String> clauses(String source) {
        String text = source.replaceAll("(?s)\\x60\\x60\\x60.*?\\x60\\x60\\x60", " ")
            .replaceAll("[*#_\\x60]", "")
            .replaceAll("(?:https?://|www\\.)\\S+", " ")
            .replaceAll("[\\p{So}\\p{Cs}\\uFE0F]", "")
            .trim();
        List<String> result = new ArrayList<>();
        StringBuilder pending = new StringBuilder();
        for (String sentence : SENTENCES.split(text)) {
            String next = sentence.trim();
            while (next.length() > 220) {
                int boundary = next.lastIndexOf(' ', 220);
                if (boundary < 100) boundary = next.offsetByCodePoints(0, 150);
                append(result, pending, next.substring(0, boundary).trim());
                next = next.substring(boundary).trim();
            }
            append(result, pending, next);
        }
        if (pending.length() > 0) result.add(pending.toString());
        return result;
    }

    private static void append(List<String> result, StringBuilder pending, String phrase) {
        if (phrase.isEmpty()) return;
        if (pending.length() + phrase.length() + 1 > 220) {
            result.add(pending.toString());
            pending.setLength(0);
        }
        if (pending.length() > 0) pending.append(' ');
        pending.append(phrase);
    }

    static Playback play(Context context, short[] pcm, CancellationSignal cancel, Consumer<Float> mouth,
                         Runnable starting, Runnable playing) throws IOException {
        AudioManager audio = context.getSystemService(AudioManager.class);
        if (audio.getStreamVolume(AudioManager.STREAM_MUSIC) == 0 || audio.isStreamMute(AudioManager.STREAM_MUSIC)) {
            throw new IOException("Media audio is muted. Turn up media volume to hear AURA.");
        }
        AtomicBoolean lostFocus = new AtomicBoolean();
        AudioFocusRequest focus = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
            .setAudioAttributes(AUDIO).setOnAudioFocusChangeListener(change -> {
                if (change == AudioManager.AUDIOFOCUS_LOSS || change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT) lostFocus.set(true);
            }).build();
        if (audio.requestAudioFocus(focus) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
            throw new IOException("Android couldn’t give AURA the audio output. Try again when other audio is done.");
        }
        AudioTrack track = null;
        try {
            track = new AudioTrack.Builder().setAudioAttributes(AUDIO)
                .setAudioFormat(new AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(NativeVoice.SAMPLE_RATE).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                .setTransferMode(AudioTrack.MODE_STATIC).setBufferSizeInBytes(pcm.length * 2).build();
            if (track.write(pcm, 0, pcm.length) != pcm.length) throw new IOException("Audio playback could not start.");
            if (cancel.isCanceled()) return new Playback(0, 0);
            starting.run();
            track.play();
            long deadline = SystemClock.elapsedRealtime() + (1000L * pcm.length / NativeVoice.SAMPLE_RATE) + 2500;
            int framesPlayed = 0;
            while (!cancel.isCanceled() && !lostFocus.get() && SystemClock.elapsedRealtime() < deadline) {
                int head = track.getPlaybackHeadPosition();
                if (head > 0 && framesPlayed == 0) {
                    AudioDeviceInfo route = track.getRoutedDevice();
                    Log.i("AuraVoice", "Media playback started, route=" + (route == null ? "default" : route.getType()));
                    playing.run();
                }
                framesPlayed = Math.max(framesPlayed, head);
                if (head >= pcm.length) break;
                int limit = Math.min(head + 720, pcm.length);
                double energy = 0;
                for (int i = head; i < limit; i++) energy += (double) pcm[i] * pcm[i];
                mouth.accept((float) Math.min(1, Math.sqrt(energy / (limit - head)) * 7 / Short.MAX_VALUE));
                SystemClock.sleep(33);
            }
            int underruns = track.getUnderrunCount();
            track.stop();
            if (framesPlayed < pcm.length && !cancel.isCanceled()) {
                throw new IOException(lostFocus.get() ? "Another app interrupted AURA’s audio." : "AURA’s audio did not finish playing.");
            }
            return new Playback(framesPlayed, underruns);
        } finally {
            if (track != null) track.release();
            audio.abandonAudioFocusRequest(focus);
        }
    }

    @Override public void close() {
        generator.execute(() -> {
            if (voice != null) voice.close();
        });
        generator.shutdown();
        player.shutdown();
    }
}
