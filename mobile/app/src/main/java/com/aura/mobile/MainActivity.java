package com.aura.mobile;

import android.Manifest;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.database.sqlite.SQLiteException;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.os.Handler;
import android.os.Looper;
import android.provider.OpenableColumns;
import android.speech.SpeechRecognizer;
import android.text.InputType;
import android.util.Log;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.Switch;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.security.GeneralSecurityException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

public final class MainActivity extends ComponentActivity {
    private static final int CAMERA_PERMISSION = 10, MIC_PERMISSION = 11, IMPORT_VOICE = 12, IMPORT_MEMORY = 13;
    private final ExecutorService chatWorker = Executors.newSingleThreadExecutor();
    private final ExecutorService filesWorker = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private final Runnable resumeMic = this::listen;
    private final Runnable hideControls = () -> hideControlsIfTalking();
    private final List<AuraChat.Message> history = new ArrayList<>();
    private SharedPreferences settings;
    private ApiKeyStore keys;
    private String apiKey = "";
    private String model;
    private SpeechLanguage micLanguage;
    private boolean speak, autoHideControls;
    private VoiceModels models;
    private AuraMemory memory;
    private VoiceOutput voice;
    private CompanionScreen screen;
    private LiveCamera camera;
    private ConversationMic mic;
    private boolean cameraOpen, talking, installing, destroying;
    private Boolean lastReportedFront;
    private CancellationSignal active;
    private TextView pendingReply;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        settings = getSharedPreferences("aura", MODE_PRIVATE);
        keys = new ApiKeyStore(settings);
        model = settings.getString("model", AuraChat.DEFAULT_MODEL);
        micLanguage = SpeechLanguage.fromTag(settings.getString("micLanguage", ""));
        speak = settings.getBoolean("voice", true);
        autoHideControls = settings.getBoolean("autoHideControls", true);
        models = new VoiceModels(this);
        memory = new AuraMemory(this);
        voice = new VoiceOutput(this, models);
        mic = new ConversationMic(this);
        camera = new LiveCamera(this, settings.getBoolean("frontCamera", false), cameraState -> {
            if (screen != null) screen.setCamera(cameraOpen, cameraState);
            if (cameraState.streaming() && (lastReportedFront == null || lastReportedFront != cameraState.front())) {
                lastReportedFront = cameraState.front();
                settings.edit().putBoolean("frontCamera", cameraState.front()).apply();
                Log.i("AuraTalk", "Live camera ready, lens=" + (cameraState.front() ? "front" : "rear"));
            }
        }, () -> {
            cameraOpen = false;
            keepScreenAwake();
            screen.setCamera(false, new LiveCamera.State(false, false, false, 1f));
            screen.setStatus("Couldn’t open the camera.");
        });
        screen = new CompanionScreen(this, camera, new CompanionScreen.Actions() {
            @Override public void settings() { openSettings(); }
            @Override public void camera() { toggleCamera(); }
            @Override public void flipCamera() { camera.flip(); }
            @Override public void talk() { toggleTalk(); }
            @Override public void interrupt() { cancelReply(); scheduleMic(150); }
            @Override public void textMode() { toggleText(); }
            @Override public void revealControls() {
                if (!talking || !autoHideControls) return;
                screen.setControlsHidden(false);
                scheduleControlsHide(6000);
            }
            @Override public void keepControlsVisible() {
                if (talking && autoHideControls && !screen.controlsHidden()) scheduleControlsHide(6000);
            }
            @Override public void send() {
                if (active != null) cancelReply();
                else sendTurn(screen.draft.getText().toString().trim(), false);
            }
        });
        getWindow().setDecorFitsSystemWindows(false);
        getWindow().setStatusBarColor(Color.TRANSPARENT);
        getWindow().setNavigationBarColor(Color.TRANSPARENT);
        setVolumeControlStream(AudioManager.STREAM_MUSIC);
        setContentView(screen);
        screen.requestFocus();
        loadHistory();
        for (AuraChat.Message message : history) screen.addMessage("user".equals(message.role()), message.text());
        if (state != null) {
            screen.setTextMode(state.getBoolean("textMode"));
            screen.draft.setText(state.getString("draft", ""));
        }
        try {
            apiKey = keys.load();
            showIdleStatus();
        } catch (GeneralSecurityException | IOException failure) {
            screen.setStatus("Enter your OpenRouter key again in Settings.");
        }
        if (speak && models.ready()) warmVoice();
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() {
                if (screen.textMode()) toggleText();
                else if (talking) endTalk();
                else if (cameraOpen) closeCamera();
                else {
                    setEnabled(false);
                    getOnBackPressedDispatcher().onBackPressed();
                }
            }
        });
    }

    private void toggleTalk() {
        if (talking) {
            endTalk();
            return;
        }
        if (apiKey.isEmpty()) {
            screen.setStatus("Add an OpenRouter API key in Settings.");
            return;
        }
        if (!speak || !models.ready()) {
            screen.setStatus(speak ? "Install AURA’s voice in Settings to talk." : "Turn on AURA’s voice in Settings to talk.");
            return;
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, MIC_PERMISSION);
            return;
        }
        cancelReply();
        hideKeyboard();
        screen.setTextMode(false);
        talking = true;
        Log.i("AuraTalk", "Hands-free session started");
        keepScreenAwake();
        screen.setTalk(true);
        screen.setCaption("");
        scheduleControlsHide(2200);
        listen();
    }

    private void listen() {
        if (!talking || destroying || active != null || mic.running()) return;
        screen.setStatus("Opening microphone…");
        mic.listen(micLanguage, new ConversationMic.Listener() {
            @Override public void ready() {
                Log.d("AuraTalk", "Microphone listening");
                screen.setStatus("Listening…");
            }
            @Override public void processing() { screen.setStatus("Transcribing…"); }
            @Override public void partial(String text) { screen.setCaption(text); }
            @Override public void result(String text) {
                if (!talking) return;
                if (text.isBlank()) scheduleMic(180);
                else sendTurn(text, true);
            }
            @Override public void error(int code) {
                if (!talking) return;
                if (code == SpeechRecognizer.ERROR_SPEECH_TIMEOUT || code == SpeechRecognizer.ERROR_NO_MATCH) {
                    scheduleMic(260);
                    return;
                }
                Log.w("AuraTalk", "Microphone error " + code);
                endTalk();
                screen.setStatus(switch (code) {
                    case SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED, SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE ->
                        "Choose an installed mic language in Settings.";
                    case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Allow microphone access to talk.";
                    default -> "The microphone couldn’t start. Tap Talk to retry.";
                });
            }
        });
    }

    private void scheduleMic(long delay) {
        main.removeCallbacks(resumeMic);
        if (talking && !destroying) main.postDelayed(resumeMic, delay);
    }

    private void endTalk() {
        talking = false;
        keepScreenAwake();
        screen.setTalk(false);
        main.removeCallbacks(hideControls);
        screen.setControlsHidden(false);
        main.removeCallbacks(resumeMic);
        mic.close();
        cancelReply();
        showIdleStatus();
    }

    private void toggleText() {
        boolean open = !screen.textMode();
        if (open) {
            if (talking) endTalk();
            screen.setTextMode(true);
            screen.scrollToLatest();
            screen.draft.requestFocus();
            screen.draft.post(() -> getSystemService(InputMethodManager.class)
                .showSoftInput(screen.draft, InputMethodManager.SHOW_IMPLICIT));
        } else {
            hideKeyboard();
            screen.setTextMode(false);
            screen.requestFocus();
        }
    }

    private void toggleCamera() {
        if (cameraOpen) {
            closeCamera();
            return;
        }
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA_PERMISSION);
            return;
        }
        cameraOpen = true;
        keepScreenAwake();
        screen.setCamera(true, new LiveCamera.State(false, false, false, 1f));
        camera.open();
    }

    private void closeCamera() {
        cameraOpen = false;
        lastReportedFront = null;
        keepScreenAwake();
        camera.close();
    }

    private void keepScreenAwake() {
        if (talking || cameraOpen) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    private void scheduleControlsHide(long delayMs) {
        main.removeCallbacks(hideControls);
        if (autoHideControls && talking) main.postDelayed(hideControls, delayMs);
    }

    private void hideControlsIfTalking() {
        if (talking && autoHideControls) screen.setControlsHidden(true);
    }

    private void sendTurn(String text, boolean fromSpeech) {
        if (text.isEmpty() || active != null) return;
        if (apiKey.isEmpty()) {
            screen.setStatus("Add an OpenRouter API key in Settings.");
            return;
        }
        Bitmap frame = cameraOpen ? camera.frame() : null;
        if (cameraOpen && frame == null) {
            screen.setStatus("Wait for the camera preview, then try again.");
            if (fromSpeech) scheduleMic(1100);
            return;
        }
        main.removeCallbacks(resumeMic);
        mic.close();
        if (fromSpeech) Log.i("AuraTalk", "Utterance accepted, camera frame=" + (frame != null));
        hideKeyboard();
        if (!fromSpeech) screen.draft.setText("");
        screen.setCaption(text);
        List<AuraChat.Message> prior = List.copyOf(history);
        String key = apiKey;
        String selectedModel = model;
        CancellationSignal request = beginReply("Thinking…");
        String shown = frame == null ? text : "Camera view attached\n" + text;
        record("user", shown);
        screen.addMessage(true, shown);
        TextView response = screen.addMessage(false, "…");
        pendingReply = response;
        AtomicReference<JSONArray> expression = new AtomicReference<>();
        VoiceOutput.Turn speech = speak && models.ready() ? speechFor(request, expression) : null;
        chatWorker.execute(() -> {
            StringBuilder reply = new StringBuilder();
            try {
                byte[] jpeg = frame == null ? null : LiveCamera.encode(frame);
                AuraMemory.Snapshot recalled = memory.snapshot(16);
                new AuraChat().stream(key, selectedModel, prior, text, jpeg, fromSpeech, recalled, request, new AuraChat.Events() {
                    @Override public void text(String delta) {
                        boolean first = reply.length() == 0;
                        if (first && fromSpeech) Log.i("AuraTalk", "First reply text received");
                        reply.append(delta);
                        String visible = reply.toString();
                        current(request, () -> {
                            response.setText(visible);
                            if (!fromSpeech || speech == null) screen.setCaption(visible);
                            screen.scrollToLatest();
                            if (speech != null) {
                                if (first) screen.setStatus("Preparing voice…");
                                speech.feed(delta);
                            }
                        });
                    }
                    @Override public void expression(JSONArray names) {
                        expression.set(names);
                        current(request, () -> screen.avatar.expression(names));
                    }
                    @Override public boolean remember(String fact, String category) {
                        if (request.isCanceled()) return false;
                        try {
                            return memory.remember(fact, category);
                        } catch (SQLiteException failure) {
                            Log.w("AuraTalk", "Local memory write failed");
                            return false;
                        }
                    }
                });
                String answer = reply.toString().trim();
                current(request, () -> {
                    if (answer.isEmpty()) {
                        failReply(request, "The model returned no spoken reply.");
                        return;
                    }
                    response.setText(answer);
                    pendingReply = null;
                    record("assistant", answer);
                    if (speech == null) finishReply(request);
                    else speech.finish();
                });
            } catch (IOException | JSONException | RuntimeException failure) {
                current(request, () -> failReply(request, message(failure, "AURA couldn’t connect.")));
            }
        });
    }

    private VoiceOutput.Turn speechFor(CancellationSignal request, AtomicReference<JSONArray> expression) {
        AtomicBoolean firstPlayback = new AtomicBoolean(true);
        return voice.turn(request, level -> current(request, () -> screen.avatar.mouth(level)),
            clause -> current(request, () -> {
                screen.setCaption(clause);
                screen.setStatus("AURA is speaking");
                JSONArray names = expression.get();
                if (firstPlayback.getAndSet(false) && names != null) screen.avatar.expression(names);
            }),
            error -> current(request, () -> failReply(request, error == null ? "AURA’s audio could not play." : error)),
            () -> current(request, () -> finishReply(request)));
    }

    private CancellationSignal beginReply(String label) {
        active = new CancellationSignal();
        screen.setBusy(true, talking);
        screen.setStatus(label);
        return active;
    }

    private void current(CancellationSignal request, Runnable event) {
        runOnUiThread(() -> {
            if (!destroying && active == request && !request.isCanceled()) event.run();
        });
    }

    private void finishReply(CancellationSignal request) {
        if (active != request) return;
        active = null;
        screen.setBusy(false, talking);
        screen.avatar.mouth(0);
        showIdleStatus();
        scheduleMic(230);
    }

    private void failReply(CancellationSignal request, String error) {
        if (active != request) return;
        Log.w("AuraTalk", "Reply failed: " + error);
        if (talking) endTalk();
        else cancelReply();
        screen.setStatus(error);
    }

    private void cancelReply() {
        if (active != null) {
            CancellationSignal request = active;
            active = null;
            new Thread(request::cancel, "aura-cancel").start();
        }
        if (pendingReply != null) {
            if ("…".contentEquals(pendingReply.getText())) screen.messages.removeView(pendingReply);
            pendingReply = null;
        }
        screen.setBusy(false, talking);
        screen.avatar.mouth(0);
        showIdleStatus();
    }

    private void hideKeyboard() {
        getSystemService(InputMethodManager.class).hideSoftInputFromWindow(screen.draft.getWindowToken(), 0);
    }

    private void openSettings() {
        if (talking) endTalk();
        var fields = CompanionScreen.column(this);
        fields.setPadding(dp(22), 0, dp(22), dp(10));
        EditText keyField = new EditText(this);
        keyField.setHint("OpenRouter API key");
        keyField.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        keyField.setSingleLine();
        keyField.setText(apiKey);
        fields.addView(keyField);
        EditText modelField = new EditText(this);
        modelField.setHint("OpenRouter model ID");
        modelField.setSingleLine();
        modelField.setText(model);
        fields.addView(modelField);
        fields.addView(CompanionScreen.label(this, "Mic language", 14, CompanionScreen.MUTED));
        Spinner languageField = new Spinner(this);
        SpeechLanguage[] languages = SpeechLanguage.values();
        String[] labels = new String[languages.length];
        for (int i = 0; i < labels.length; i++) labels[i] = languages[i].label;
        ArrayAdapter<String> choices = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, labels);
        choices.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        languageField.setAdapter(choices);
        languageField.setSelection(micLanguage.ordinal());
        languageField.setMinimumHeight(dp(48));
        fields.addView(languageField);
        Switch voiceSwitch = new Switch(this);
        voiceSwitch.setText("Speak with AURA’s local voice");
        voiceSwitch.setChecked(speak);
        voiceSwitch.setMinHeight(dp(48));
        fields.addView(voiceSwitch);
        Switch hideSwitch = new Switch(this);
        hideSwitch.setText("Auto-hide controls during Talk");
        hideSwitch.setChecked(autoHideControls);
        hideSwitch.setMinHeight(dp(48));
        fields.addView(hideSwitch);
        fields.addView(CompanionScreen.label(this, "Double-tap the screen to show controls.", 14, CompanionScreen.MUTED));
        ScrollView scroll = new ScrollView(this);
        scroll.addView(fields);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("Settings").setView(scroll)
            .setNegativeButton("Cancel", null).setPositiveButton("Save", null).create();
        fields.addView(CompanionScreen.label(this, models.ready() ? "Voice models installed" : "Voice needs 920 MB of model files.", 14,
            CompanionScreen.MUTED));
        if (models.ready()) {
            fields.addView(settingsButton("Test voice", () -> {
                dialog.dismiss();
                testVoice();
            }));
        } else {
            fields.addView(settingsButton("Download voice models", () -> {
                dialog.dismiss();
                installModels(null);
            }));
            fields.addView(settingsButton("Import voice ZIP or GGUF", () -> {
                dialog.dismiss();
                selectFile(IMPORT_VOICE);
            }));
        }
        fields.addView(CompanionScreen.label(this, "While the camera is on, AURA receives a current frame with each message.", 14,
            CompanionScreen.MUTED));
        fields.addView(settingsButton("Saved memories", () -> {
            dialog.dismiss();
            showMemories();
        }));
        fields.addView(settingsButton("Clear chat history", () -> new AlertDialog.Builder(this)
            .setMessage("Clear this phone’s AURA chat history?")
            .setNegativeButton("Cancel", null).setPositiveButton("Clear", (confirm, which) -> {
                cancelReply();
                history.clear();
                screen.messages.removeAllViews();
                saveHistory();
                dialog.dismiss();
            }).show()));
        dialog.show();
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
            String nextKey = keyField.getText().toString().trim();
            try {
                if (!nextKey.equals(apiKey)) keys.save(nextKey);
                apiKey = nextKey;
                String nextModel = modelField.getText().toString().trim();
                model = nextModel.isEmpty() ? AuraChat.DEFAULT_MODEL : nextModel;
                micLanguage = languages[languageField.getSelectedItemPosition()];
                speak = voiceSwitch.isChecked();
                autoHideControls = hideSwitch.isChecked();
                settings.edit().putString("model", model).putString("micLanguage", micLanguage.tag)
                    .putBoolean("voice", speak).putBoolean("autoHideControls", autoHideControls).apply();
                if (!speak) cancelReply();
                if (speak && models.ready()) warmVoice();
                if (active == null) showIdleStatus();
                dialog.dismiss();
            } catch (GeneralSecurityException | IOException failure) {
                keyField.setError("Couldn’t save the API key.");
            }
        });
    }

    private void showMemories() {
        filesWorker.execute(() -> {
            try {
                AuraMemory.Snapshot saved = memory.snapshot(50);
                List<String> lines = new ArrayList<>();
                if (!saved.userName().isBlank()) lines.add(saved.userName());
                for (AuraMemory.Fact fact : saved.facts()) lines.add(fact.content());
                runOnUiThread(() -> {
                    if (destroying) return;
                    AlertDialog.Builder dialog = new AlertDialog.Builder(this).setTitle("Saved memories")
                        .setPositiveButton("Done", null)
                        .setNeutralButton("Import desktop", (ignored, button) -> selectFile(IMPORT_MEMORY));
                    if (lines.isEmpty()) dialog.setMessage("Ask AURA to remember something, or import your desktop memory database.");
                    else dialog.setItems(lines.toArray(new String[0]), null)
                        .setNegativeButton("Clear", (ignored, button) -> confirmClearMemory());
                    dialog.show();
                });
            } catch (SQLiteException failure) {
                runOnUiThread(() -> { if (!destroying) screen.setStatus("Couldn’t read saved memories."); });
            }
        });
    }

    private void confirmClearMemory() {
        new AlertDialog.Builder(this).setMessage("Clear the saved facts and imported name on this phone?")
            .setNegativeButton("Cancel", null).setPositiveButton("Clear", (dialog, button) -> {
                filesWorker.execute(() -> {
                    try {
                        memory.clear();
                        runOnUiThread(() -> { if (!destroying) screen.setStatus("Saved memories cleared."); });
                    } catch (SQLiteException failure) {
                        runOnUiThread(() -> { if (!destroying) screen.setStatus("Couldn’t clear saved memories."); });
                    }
                });
            }).show();
    }

    private android.widget.Button settingsButton(String text, Runnable action) {
        return CompanionScreen.button(this, text, CompanionScreen.SURFACE, CompanionScreen.INK, view -> action.run());
    }

    private void testVoice() {
        cancelReply();
        String sample = micLanguage == SpeechLanguage.JAPANESE ? "おや？ ここにいるよ。" : "Oya? I'm right here.";
        CancellationSignal request = beginReply("Preparing voice…");
        screen.setCaption(sample);
        VoiceOutput.Turn speech = speechFor(request, new AtomicReference<>());
        speech.feed(sample);
        speech.finish();
    }

    private void warmVoice() {
        voice.warm(error -> runOnUiThread(() -> {
            if (!destroying && active == null && error != null) screen.setStatus(error);
        }));
    }

    private void selectFile(int request) {
        try {
            startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                .setType("*/*"), request);
        } catch (ActivityNotFoundException failure) {
            screen.setStatus("Android’s file picker is unavailable.");
        }
    }

    private void installModels(Uri uri) {
        if (installing) return;
        installing = true;
        screen.setStatus("Preparing voice models…");
        filesWorker.execute(() -> {
            String result;
            try {
                VoiceModels.Progress progress = update -> runOnUiThread(() -> {
                    if (!destroying) screen.setStatus(update);
                });
                if (uri == null) models.download(progress);
                else models.importFile(uri, displayName(uri), progress);
                result = models.ready() ? "Voice models ready" : "Import the remaining GGUF model file.";
            } catch (IOException | RuntimeException failure) {
                result = message(failure, "Couldn’t install the voice models.");
            }
            String installed = result;
            runOnUiThread(() -> {
                if (destroying) return;
                installing = false;
                screen.setStatus(installed);
                if (speak && models.ready()) warmVoice();
            });
        });
    }

    private String displayName(Uri uri) {
        try (Cursor cursor = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            return cursor != null && cursor.moveToFirst() ? cursor.getString(0) : "";
        }
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (result != RESULT_OK || data == null || data.getData() == null) return;
        if (request == IMPORT_VOICE) installModels(data.getData());
        else if (request == IMPORT_MEMORY) importDesktopMemory(data.getData());
    }

    private void importDesktopMemory(Uri uri) {
        screen.setStatus("Importing saved memories…");
        filesWorker.execute(() -> {
            try {
                AuraMemory.ImportResult result = memory.importDesktop(uri);
                String added = "Imported " + result.added() + (result.added() == 1 ? " saved fact" : " saved facts");
                if (result.importedName()) added += " and your desktop name";
                String status = added + ".";
                runOnUiThread(() -> { if (!destroying) screen.setStatus(status); });
            } catch (IOException | RuntimeException failure) {
                runOnUiThread(() -> {
                    if (!destroying) screen.setStatus(message(failure, "Couldn’t import the desktop memories."));
                });
            }
        });
    }

    @Override public void onRequestPermissionsResult(int request, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(request, permissions, results);
        boolean allowed = results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED;
        if (request == MIC_PERMISSION) {
            if (allowed) toggleTalk();
            else screen.setStatus("Allow microphone access to talk.");
        } else if (request == CAMERA_PERMISSION) {
            if (allowed) toggleCamera();
            else screen.setStatus("Allow camera access for live vision.");
        }
    }

    private void loadHistory() {
        try {
            JSONArray saved = new JSONArray(settings.getString("history", "[]"));
            for (int i = 0; i < saved.length(); i++) {
                JSONObject item = saved.getJSONObject(i);
                history.add(new AuraChat.Message(item.getString("role"), item.getString("text")));
            }
        } catch (JSONException failure) {
            history.clear();
        }
    }

    private void record(String role, String text) {
        history.add(new AuraChat.Message(role, text));
        if (history.size() > 60) history.remove(0);
        saveHistory();
    }

    private void saveHistory() {
        JSONArray saved = new JSONArray();
        try {
            for (AuraChat.Message message : history) {
                saved.put(new JSONObject().put("role", message.role()).put("text", message.text()));
            }
            settings.edit().putString("history", saved.toString()).apply();
        } catch (JSONException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private void showIdleStatus() {
        String status = "";
        if (apiKey.isBlank()) status = "Add an OpenRouter key in Settings.";
        else if (speak && !models.ready() && !installing) status = "Set up AURA’s local voice in Settings.";
        else if (talking) status = "Mic on";
        screen.setStatus(status);
    }

    private static String message(Throwable failure, String fallback) {
        return failure.getMessage() == null || failure.getMessage().isBlank() ? fallback : failure.getMessage();
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        state.putString("draft", screen.draft.getText().toString());
        state.putBoolean("textMode", screen.textMode());
        super.onSaveInstanceState(state);
    }

    @Override protected void onStop() {
        endTalk();
        closeCamera();
        super.onStop();
    }

    @Override protected void onDestroy() {
        destroying = true;
        chatWorker.shutdown();
        filesWorker.shutdownNow();
        voice.close();
        memory.close();
        screen.removeView(screen.avatar);
        screen.avatar.destroy();
        super.onDestroy();
    }
}
