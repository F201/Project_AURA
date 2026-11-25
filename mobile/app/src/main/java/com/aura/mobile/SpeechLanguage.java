package com.aura.mobile;

import android.content.Intent;
import android.speech.RecognizerIntent;

enum SpeechLanguage {
    DEVICE("", "Device language"),
    INDONESIAN("id-ID", "Bahasa Indonesia"),
    ENGLISH("en-US", "English"),
    JAPANESE("ja-JP", "日本語");

    final String tag;
    final String label;

    SpeechLanguage(String tag, String label) {
        this.tag = tag;
        this.label = label;
    }

    static SpeechLanguage fromTag(String tag) {
        for (SpeechLanguage language : values()) {
            if (language.tag.equals(tag)) return language;
        }
        return DEVICE;
    }

    Intent recognitionIntent() {
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            .putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        if (!tag.isEmpty()) intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, tag);
        return intent;
    }
}
