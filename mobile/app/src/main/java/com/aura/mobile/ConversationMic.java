package com.aura.mobile;

import android.content.Context;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.SpeechRecognizer;

import java.util.List;

final class ConversationMic implements AutoCloseable {
    interface Listener {
        void ready();
        void processing();
        void partial(String text);
        void result(String text);
        void error(int code);
    }

    private final Context context;
    private SpeechRecognizer current;

    ConversationMic(Context context) {
        this.context = context;
    }

    boolean running() {
        return current != null;
    }

    void listen(SpeechLanguage language, Listener events) {
        boolean local = SpeechRecognizer.isOnDeviceRecognitionAvailable(context);
        if (!local && !SpeechRecognizer.isRecognitionAvailable(context)) {
            events.error(SpeechRecognizer.ERROR_CLIENT);
            return;
        }
        start(language, events, local);
    }

    private void start(SpeechLanguage language, Listener events, boolean local) {
        close();
        SpeechRecognizer recognizer;
        try {
            recognizer = local ? SpeechRecognizer.createOnDeviceSpeechRecognizer(context)
                : SpeechRecognizer.createSpeechRecognizer(context);
        } catch (RuntimeException failure) {
            events.error(SpeechRecognizer.ERROR_CLIENT);
            return;
        }
        current = recognizer;
        recognizer.setRecognitionListener(new RecognitionListener() {
            @Override public void onReadyForSpeech(Bundle info) {
                if (current == recognizer) events.ready();
            }
            @Override public void onBeginningOfSpeech() {}
            @Override public void onRmsChanged(float rms) {}
            @Override public void onBufferReceived(byte[] buffer) {}
            @Override public void onEvent(int type, Bundle info) {}
            @Override public void onEndOfSpeech() {
                if (current == recognizer) events.processing();
            }
            @Override public void onPartialResults(Bundle results) {
                if (current == recognizer) events.partial(firstResult(results));
            }
            @Override public void onError(int code) {
                if (current != recognizer) return;
                close();
                if (local && (code == SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED
                    || code == SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE)
                    && SpeechRecognizer.isRecognitionAvailable(context)) {
                    start(language, events, false);
                } else {
                    events.error(code);
                }
            }
            @Override public void onResults(Bundle results) {
                if (current != recognizer) return;
                close();
                events.result(firstResult(results));
            }
        });
        try {
            recognizer.startListening(language.recognitionIntent());
        } catch (RuntimeException failure) {
            close();
            events.error(SpeechRecognizer.ERROR_CLIENT);
        }
    }

    private static String firstResult(Bundle results) {
        List<String> found = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        return found == null || found.isEmpty() ? "" : found.get(0).trim();
    }

    @Override public void close() {
        SpeechRecognizer previous = current;
        current = null;
        if (previous != null) previous.destroy();
    }
}
