package com.aura.mobile;

import static org.junit.Assert.*;

import android.content.Context;
import android.content.ContentValues;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.os.CancellationSignal;
import android.os.SystemClock;
import android.speech.RecognizerIntent;
import android.util.Base64;
import android.util.Log;
import android.view.InputDevice;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.TextView;

import androidx.test.core.app.ActivityScenario;
import androidx.camera.view.PreviewView;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Assume;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.AtomicLong;

@RunWith(AndroidJUnit4.class)
public final class MobileTest {
    private static Context context() {
        return InstrumentationRegistry.getInstrumentation().getTargetContext();
    }

    @Test public void cameraFrameIsCompressedInMemory() throws Exception {
        Bitmap sample = Bitmap.createBitmap(400, 500, Bitmap.Config.ARGB_8888);
        sample.eraseColor(Color.MAGENTA);
        byte[] jpeg = LiveCamera.encode(sample);
        assertTrue(sample.isRecycled());
        assertEquals((byte) 0xff, jpeg[0]);
        assertEquals((byte) 0xd8, jpeg[1]);
    }

    @Test public void cameraShowsAnActualPreviewAndCloses() throws Exception {
        Assume.assumeTrue("true".equals(InstrumentationRegistry.getArguments().getString("cameraHardware")));
        InstrumentationRegistry.getInstrumentation().getUiAutomation()
            .grantRuntimePermission(context().getPackageName(), android.Manifest.permission.CAMERA);
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            CountDownLatch streaming = new CountDownLatch(1);
            scenario.onActivity(activity -> {
                View root = activity.findViewById(android.R.id.content);
                PreviewView preview = find(root, PreviewView.class, null);
                assertFalse(preview.isShown());
                preview.getPreviewStreamState().observe(activity, state -> {
                    if (state == PreviewView.StreamState.STREAMING) streaming.countDown();
                });
                find(root, Button.class, "Camera").performClick();
            });
            assertTrue("CameraX should deliver a preview frame", streaming.await(15, TimeUnit.SECONDS));
            scenario.onActivity(activity -> {
                View root = activity.findViewById(android.R.id.content);
                PreviewView preview = find(root, PreviewView.class, null);
                Bitmap frame = preview.getBitmap();
                assertNotNull("The visible camera should supply the current frame", frame);
                assertTrue(frame.getWidth() > 0 && frame.getHeight() > 0);
                frame.recycle();
            });
            scenario.onActivity(activity -> {
                View root = activity.findViewById(android.R.id.content);
                ImageButton flip = findDescription(root, ImageButton.class, "Switch to front camera");
                if (flip != null && flip.isShown()) flip.performClick();
            });
            if (context().getPackageManager().hasSystemFeature(android.content.pm.PackageManager.FEATURE_CAMERA_FRONT)) {
                long deadline = SystemClock.elapsedRealtime() + 10_000;
                AtomicBoolean frontPreview = new AtomicBoolean();
                do {
                    scenario.onActivity(activity -> {
                        View root = activity.findViewById(android.R.id.content);
                        TextView label = find(root, TextView.class, "Front camera");
                        frontPreview.set(label != null && label.isShown());
                    });
                    if (!frontPreview.get()) SystemClock.sleep(80);
                } while (!frontPreview.get() && SystemClock.elapsedRealtime() < deadline);
                assertTrue("Switching the preview should show the front lens", frontPreview.get());
            }
            int[] center = new int[2];
            scenario.onActivity(activity -> {
                PreviewView preview = find(activity.findViewById(android.R.id.content), PreviewView.class, null);
                preview.getLocationOnScreen(center);
                center[0] += preview.getWidth() / 2;
                center[1] += preview.getHeight() / 2;
            });
            pinch(center[0], center[1], 24, 102);
            scenario.onActivity(activity -> {
                View root = activity.findViewById(android.R.id.content);
                assertTrue("Pinch-out should increase camera zoom", cameraShowsZoom(root));
            });
            pinch(center[0], center[1], 102, 16);
            scenario.onActivity(activity -> {
                View root = activity.findViewById(android.R.id.content);
                PreviewView preview = find(root, PreviewView.class, null);
                find(root, Button.class, "Camera").performClick();
                assertFalse(preview.isShown());
            });
        }
    }

    private static boolean cameraShowsZoom(View root) {
        if (root instanceof TextView label && label.getText().toString().matches("(Front|Rear) camera .*×")) return true;
        if (root instanceof ViewGroup group) {
            for (int i = 0; i < group.getChildCount(); i++) {
                if (cameraShowsZoom(group.getChildAt(i))) return true;
            }
        }
        return false;
    }

    private static void pinch(int x, int y, int start, int end) {
        long down = SystemClock.uptimeMillis();
        sendTouch(down, MotionEvent.ACTION_DOWN, 1, x, y, start);
        sendTouch(down, MotionEvent.ACTION_POINTER_DOWN | (1 << MotionEvent.ACTION_POINTER_INDEX_SHIFT), 2, x, y, start);
        for (int step = 1; step <= 8; step++) {
            SystemClock.sleep(24);
            sendTouch(down, MotionEvent.ACTION_MOVE, 2, x, y, start + (end - start) * step / 8);
        }
        sendTouch(down, MotionEvent.ACTION_POINTER_UP | (1 << MotionEvent.ACTION_POINTER_INDEX_SHIFT), 2, x, y, end);
        sendTouch(down, MotionEvent.ACTION_UP, 1, x, y, end);
    }

    private static void sendTouch(long down, int action, int count, int x, int y, int distance) {
        MotionEvent.PointerProperties[] pointers = new MotionEvent.PointerProperties[count];
        MotionEvent.PointerCoords[] positions = new MotionEvent.PointerCoords[count];
        for (int i = 0; i < count; i++) {
            MotionEvent.PointerProperties pointer = new MotionEvent.PointerProperties();
            pointer.id = i;
            pointer.toolType = MotionEvent.TOOL_TYPE_FINGER;
            pointers[i] = pointer;
            MotionEvent.PointerCoords point = new MotionEvent.PointerCoords();
            point.x = x + (i == 0 ? -distance : distance);
            point.y = y;
            point.pressure = 1;
            point.size = 1;
            positions[i] = point;
        }
        MotionEvent event = MotionEvent.obtain(down, SystemClock.uptimeMillis(), action, count, pointers, positions,
            0, 0, 1, 1, 0, 0, InputDevice.SOURCE_TOUCHSCREEN, 0);
        try {
            InstrumentationRegistry.getInstrumentation().sendPointerSync(event);
        } finally {
            event.recycle();
        }
    }

    @Test public void cameraBytesAreAttachedOnlyToTheCurrentMessage() throws Exception {
        byte[] photo = {1, 2, 3, 4};
        List<AuraChat.Message> history = List.of(new AuraChat.Message("user", "Previous message"));
        JSONArray withPhoto = AuraChat.payload(AuraChat.DEFAULT_MODEL, history, "What is this?", photo).getJSONArray("messages");
        assertEquals("Previous message", withPhoto.getJSONObject(1).getString("content"));
        JSONArray current = withPhoto.getJSONObject(2).getJSONArray("content");
        assertEquals("What is this?", current.getJSONObject(0).getString("text"));
        String uri = current.getJSONObject(1).getJSONObject("image_url").getString("url");
        assertTrue(uri.startsWith("data:image/jpeg;base64,"));
        assertArrayEquals(photo, Base64.decode(uri.split(",")[1], Base64.NO_WRAP));
        JSONArray textOnly = AuraChat.payload(AuraChat.DEFAULT_MODEL, history, "Hello", null).getJSONArray("messages");
        assertEquals("Hello", textOnly.getJSONObject(2).getString("content"));
    }

    @Test public void readsStreamedTextAndValidAvatarExpressions() throws Exception {
        String events = """
            : waiting
            data: {"choices":[{"delta":{"content":"Oya? "}}]}
            data: {"choices":[{"delta":{"content":"A red apple."}}]}
            data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"name":"set_avatar_expression","arguments":"{\\"names\\":["}}]}}]}
            data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"SmileLock\\",\\"invalid\\"]}"}}]}}]}
            data: {"choices":[{"delta":{},"finish_reason":"stop"}]}
            data: [DONE]
            """;
        StringBuilder reply = new StringBuilder();
        AtomicReference<JSONArray> expression = new AtomicReference<>();
        AuraChat.Events listener = new AuraChat.Events() {
            @Override public void text(String delta) { reply.append(delta); }
            @Override public void expression(JSONArray names) { expression.set(names); }
        };
        AuraChat.readEvents(bytes(events), new CancellationSignal(), listener);
        assertEquals("Oya? A red apple.", reply.toString());
        assertEquals("[\"SmileLock\"]", expression.get().toString());
        assertThrows(IOException.class, () -> AuraChat.readEvents(bytes("data: {\"error\":{}}\n"), new CancellationSignal(), listener));
        assertThrows(IOException.class, () -> AuraChat.readEvents(bytes(": truncated\n"), new CancellationSignal(), listener));
        CancellationSignal stopped = new CancellationSignal();
        stopped.cancel();
        AuraChat.readEvents(bytes(events), stopped, listener);
        assertEquals("Oya? A red apple.", reply.toString());
    }

    @Test public void apiKeyIsEncryptedAndRemovable() throws Exception {
        var prefs = context().getSharedPreferences("aura-test-vault", Context.MODE_PRIVATE);
        ApiKeyStore store = new ApiKeyStore(prefs);
        store.save("sample-key-for-encryption-test");
        assertEquals("sample-key-for-encryption-test", new ApiKeyStore(prefs).load());
        assertFalse(prefs.getString("apiKey", "").contains("sample-key"));
        store.save("");
        assertEquals("", new ApiKeyStore(prefs).load());
    }

    @Test public void draftSurvivesRecreationAndMissingKeyKeepsItLocal() throws Exception {
        Assume.assumeTrue(new ApiKeyStore(context().getSharedPreferences("aura", Context.MODE_PRIVATE)).load().isEmpty());
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.findViewById(android.R.id.content);
                find(root, Button.class, "Type").performClick();
                EditText draft = find(root, EditText.class, null);
                draft.setText("Hello AURA");
                find(root, Button.class, "Send").performClick();
                assertNotNull(find(root, TextView.class, "Add an OpenRouter API key in Settings."));
                assertEquals("Hello AURA", draft.getText().toString());
            });
            scenario.recreate();
            scenario.onActivity(activity -> {
                View root = activity.findViewById(android.R.id.content);
                assertEquals("Hello AURA", find(root, EditText.class, null).getText().toString());
            });
        }
    }

    @Test public void live2dLoadsInsideTheApp() throws Exception {
        CountDownLatch ready = new CountDownLatch(1);
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> pollAvatar(find(activity.findViewById(android.R.id.content), AvatarView.class, null),
                ready, SystemClock.elapsedRealtime() + 15_000));
            assertTrue("The packaged Live2D model should load", ready.await(17, TimeUnit.SECONDS));
        }
    }

    @Test public void llmToolCallsAnimateTheActualAvatar() throws Exception {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            inspectAvatar(scenario);
            fixtureToolCall(scenario, "SmileLock");
            awaitAvatar(scenario, "p('ParamMouthForm') > 0.7 && p('ParamEyeLSmile') > 0.5");
            fixtureToolCall(scenario, "Angry");
            awaitAvatar(scenario, "p('ParamMouthForm') < -0.5 && p('ParamBrowLAngle') < -0.6");
            fixtureToolCall(scenario, "SadLock");
            awaitAvatar(scenario, "p('ParamMouthForm') < -0.6 && p('ParamBrowLAngle') > 0.5");
            fixtureToolCall(scenario, "Ghost", "Shadow");
            awaitAvatar(scenario, "p('Param80') > 0.7 && p('Param2') > 0.7");
            fixtureToolCall(scenario, "neutral");
            awaitAvatar(scenario, "p('Param80') < 0.1 && p('Param2') < 0.1");
            fixtureToolCall(scenario, "wink");
            awaitAvatar(scenario, "p('ParamEyeLOpen') < 0.3 && p('ParamEyeROpen') > 0.5 && p('ParamMouthForm') > 0.5");
        }
    }

    @Test public void liveOpenRouterToolCallAnimatesTheAvatar() throws Exception {
        Assume.assumeTrue("true".equals(InstrumentationRegistry.getArguments().getString("liveOpenRouter")));
        var prefs = context().getSharedPreferences("aura", Context.MODE_PRIVATE);
        String key = new ApiKeyStore(prefs).load();
        assertFalse("Enter the OpenRouter key in AURA Settings before running the live test", key.isEmpty());
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            inspectAvatar(scenario);
            StringBuilder reply = new StringBuilder();
            AtomicReference<JSONArray> expression = new AtomicReference<>();
            String prompt = "Untuk tes integrasi, panggil set_avatar_expression dengan names [\"Angry\"]. "
                + "Lalu jawab dalam bahasa Inggris. Apa warna dan bentuk gambar ini?";
            new AuraChat().stream(key, prefs.getString("model", AuraChat.DEFAULT_MODEL), List.of(), prompt, testImage(),
                new CancellationSignal(), new AuraChat.Events() {
                    @Override public void text(String delta) { reply.append(delta); }
                    @Override public void expression(JSONArray names) { expression.set(names); }
                });
            String answer = reply.toString().toLowerCase(Locale.ROOT);
            assertTrue("The model should identify the test image in English",
                answer.contains("blue") && answer.contains("square"));
            assertNotNull("The model should emit an expression tool call", expression.get());
            assertEquals("Angry", expression.get().optString(0));
            scenario.onActivity(activity -> avatar(activity).expression(expression.get()));
            awaitAvatar(scenario, "p('ParamMouthForm') < -0.5 && p('ParamBrowLAngle') < -0.6");
        }
    }

    private static byte[] testImage() {
        Bitmap image = Bitmap.createBitmap(224, 224, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(image);
        canvas.drawColor(Color.WHITE);
        Paint paint = new Paint();
        paint.setColor(Color.BLUE);
        canvas.drawRect(48, 48, 176, 176, paint);
        ByteArrayOutputStream jpeg = new ByteArrayOutputStream();
        assertTrue(image.compress(Bitmap.CompressFormat.JPEG, 90, jpeg));
        image.recycle();
        return jpeg.toByteArray();
    }

    @Test public void limitsVoiceSegmentsAndPreservesShortReplies() {
        assertEquals(List.of("Oya? I'm here."), VoiceOutput.clauses("**Oya?** I'm here."));
        assertTrue(VoiceOutput.clauses("https://example.org").isEmpty());
        List<String> paragraphs = VoiceOutput.clauses("日本語".repeat(100));
        assertTrue(paragraphs.size() > 1);
        assertTrue(paragraphs.stream().allMatch(text -> !text.isEmpty() && text.length() <= 220));
        assertEquals(0, VoiceOutput.speechBoundary("Oya?"));
        assertEquals("Oya? I'm right here. ".length(), VoiceOutput.speechBoundary("Oya? I'm right here. How is it going?"));
    }

    @Test public void passesIndonesianDictationAndChatInputToTheRightServices() throws Exception {
        assertEquals("id-ID", SpeechLanguage.INDONESIAN.recognitionIntent().getStringExtra(RecognizerIntent.EXTRA_LANGUAGE));
        assertFalse(SpeechLanguage.DEVICE.recognitionIntent().hasExtra(RecognizerIntent.EXTRA_LANGUAGE));
        assertEquals(SpeechLanguage.INDONESIAN, SpeechLanguage.fromTag("id-ID"));
        String userText = "Aura, bisa bantu aku?";
        JSONArray messages = AuraChat.payload(AuraChat.DEFAULT_MODEL, List.of(), userText, null).getJSONArray("messages");
        assertEquals(userText, messages.getJSONObject(1).getString("content"));
        assertTrue(messages.getJSONObject(0).getString("content").contains("Otherwise reply in English."));
        JSONArray live = AuraChat.payload(AuraChat.DEFAULT_MODEL, List.of(), userText, testImage(), true).getJSONArray("messages");
        assertTrue(live.getJSONObject(0).getString("content").contains("This is hands-free talk."));
        assertEquals("image_url", live.getJSONObject(1).getJSONArray("content").getJSONObject(1).getString("type"));
    }

    @Test public void liveModelCanSaveAndRecallSqliteMemory() throws Exception {
        Assume.assumeTrue("true".equals(InstrumentationRegistry.getArguments().getString("liveOpenRouter")));
        var prefs = context().getSharedPreferences("aura", Context.MODE_PRIVATE);
        String key = new ApiKeyStore(prefs).load();
        assertFalse("Enter the OpenRouter key in AURA Settings before running the live test", key.isEmpty());
        String model = prefs.getString("model", AuraChat.DEFAULT_MODEL);
        String fixture = "live-memory-integration.db";
        context().deleteDatabase(fixture);
        try {
            try (AuraMemory temporary = new AuraMemory(context(), fixture)) {
                new AuraChat().stream(key, model, List.of(),
                    "Please remember this fact using remember_fact: my favorite tea is roasted barley tea.",
                    null, true, temporary.snapshot(16), new CancellationSignal(), new AuraChat.Events() {
                        @Override public void text(String delta) {}
                        @Override public void expression(JSONArray names) {}
                        @Override public boolean remember(String fact, String category) {
                            return temporary.remember(fact, category);
                        }
                    });
            }
            try (AuraMemory reopened = new AuraMemory(context(), fixture)) {
                AuraMemory.Snapshot facts = reopened.snapshot(16);
                assertTrue(facts.facts().stream().anyMatch(fact ->
                    fact.content().toLowerCase(Locale.ROOT).contains("barley")));
                StringBuilder response = new StringBuilder();
                new AuraChat().stream(key, model, List.of(), "What is my favorite tea?", null, true, facts,
                    new CancellationSignal(), new AuraChat.Events() {
                        @Override public void text(String delta) { response.append(delta); }
                        @Override public void expression(JSONArray names) {}
                    });
                assertTrue("The fresh conversation should recall the saved fact",
                    response.toString().toLowerCase(Locale.ROOT).contains("barley"));
            }
        } finally {
            context().deleteDatabase(fixture);
        }
    }

    @Test public void savedMemorySurvivesReopeningAndMergesDesktopFacts() throws Exception {
        String source = "desktop-memory-fixture.db";
        String target = "mobile-memory-fixture.db";
        context().deleteDatabase(source);
        context().deleteDatabase(target);
        try {
            try (AuraMemory desktop = new AuraMemory(context(), source)) {
                ContentValues profile = new ContentValues();
                profile.put("key", "user_name");
                profile.put("value", "AURA test account");
                desktop.getWritableDatabase().insertOrThrow("profile", null, profile);
                assertTrue(desktop.remember("The user prefers jasmine tea.", "preference"));
            }
            try (AuraMemory local = new AuraMemory(context(), target)) {
                assertTrue(local.remember("The user likes pencil sketches.", "fact"));
                AuraMemory.ImportResult imported = local.importDesktop(context().getDatabasePath(source));
                assertEquals(1, imported.added());
                assertTrue(imported.importedName());
                assertEquals(0, local.importDesktop(context().getDatabasePath(source)).added());
            }
            try (AuraMemory reopened = new AuraMemory(context(), target)) {
                AuraMemory.Snapshot saved = reopened.snapshot(16);
                assertEquals("AURA test account", saved.userName());
                assertEquals(2, saved.facts().size());
                JSONArray messages = AuraChat.payload(AuraChat.DEFAULT_MODEL, List.of(),
                    "What do you remember?", null, true, saved).getJSONArray("messages");
                String persona = messages.getJSONObject(0).getString("content");
                assertTrue(persona.contains("jasmine tea"));
                assertTrue(persona.contains("pencil sketches"));
                reopened.clear();
                assertEquals(AuraMemory.EMPTY, reopened.snapshot(16));
            }
        } finally {
            context().deleteDatabase(source);
            context().deleteDatabase(target);
        }
    }

    @Test public void rendersTheRealClonedVoiceOffline() throws Exception {
        VoiceModels models = new VoiceModels(context());
        if ("true".equals(InstrumentationRegistry.getArguments().getString("requireModels"))) {
            assertTrue("Import the verified voice models before running this test.", models.ready());
        } else {
            Assume.assumeTrue("Import the voice models before running this test.", models.ready());
        }
        var preferences = context().getSharedPreferences("aura", Context.MODE_PRIVATE);
        boolean hadVoiceSetting = preferences.contains("voice");
        boolean voiceEnabled = preferences.getBoolean("voice", true);
        assertTrue(preferences.edit().putBoolean("voice", false).commit());
        try (ActivityScenario<MainActivity> foreground = ActivityScenario.launch(MainActivity.class)) {
            benchmarkVoice(models);
        } finally {
            if (hadVoiceSetting) preferences.edit().putBoolean("voice", voiceEnabled).commit();
            else preferences.edit().remove("voice").commit();
        }
    }

    private static void benchmarkVoice(VoiceModels models) throws Exception {
        long started = SystemClock.elapsedRealtime();
        try (NativeVoice voice = new NativeVoice(models)) {
            long load = SystemClock.elapsedRealtime() - started;
            CancellationSignal canceled = new CancellationSignal();
            canceled.cancel();
            assertNull(voice.generate("AURA", canceled));
            String workers = InstrumentationRegistry.getArguments().getString("voiceThreads",
                Integer.toString(NativeVoice.PREFERRED_THREADS));
            String chunks = InstrumentationRegistry.getArguments().getString("voiceChunkMillis",
                Integer.toString(NativeVoice.CHUNK_MILLIS));
            String prompt = InstrumentationRegistry.getArguments().getString("voicePrompt",
                "Oya? I'm right here. Let's see what we find today!");
            for (String chunk : chunks.split(",")) {
                for (String count : workers.split(",")) {
                    measureVoice(voice, prompt, load, Integer.parseInt(count), Integer.parseInt(chunk));
                }
            }
        }
    }

    private static void measureVoice(NativeVoice voice, String prompt, long load, int threads, int chunkMillis) throws Exception {
        long[] timings = new long[4];
        long requestStart = SystemClock.elapsedRealtime();
        short[] pcm = voice.generate(prompt, new CancellationSignal(), timings, threads, 42, chunkMillis);
        assertNotNull(pcm);
        assertEquals(timings[3], pcm.length);
        assertTrue("Expected at least half a second of speech", pcm.length > NativeVoice.SAMPLE_RATE / 2);
        assertTrue(timings[0] > 0 && timings[1] >= timings[0]);
        int peak = 0;
        for (short sample : pcm) peak = Math.max(peak, Math.abs((int) sample));
        assertTrue("Samples should contain audible speech", peak > 800);
        AtomicLong firstPlayback = new AtomicLong(-1);
        VoiceOutput.Playback playback = VoiceOutput.play(context(), pcm, new CancellationSignal(), level -> {}, () -> {},
            () -> firstPlayback.set(SystemClock.elapsedRealtime() - requestStart));
        writeWav(new File(context().getCacheDir(), "aura-voice-test-" + threads + "-" + chunkMillis + ".wav"), pcm);
        double audioSeconds = pcm.length / (double) NativeVoice.SAMPLE_RATE;
        double framesPerSecond = audioSeconds * 12.5 * 1000 / timings[1];
        Log.i("AuraVoiceTest", "threads=" + threads + " chunkMillis=" + chunkMillis
            + " loadMs=" + load + " firstDecodedMs=" + timings[0]
            + " synthMs=" + timings[1] + " idealNoGapStartMs=" + timings[2] + " playbackStartMs=" + firstPlayback
            + " underruns=" + playback.underruns() + " playedFrames=" + playback.framesPlayed()
            + " sampleFrames=" + pcm.length + " audioSeconds=" + audioSeconds + " codecFramesPerSecond=" + framesPerSecond);
        assertTrue("Android should start playback", firstPlayback.get() >= 0);
        assertTrue("Android should play the full waveform", playback.framesPlayed() >= pcm.length);
        assertEquals("Playback should not starve", 0, playback.underruns());
    }

    private static void pollAvatar(AvatarView avatar, CountDownLatch ready, long deadline) {
        avatar.evaluateJavascript("window.auraAvatar?.ready === true", result -> {
            if ("true".equals(result)) ready.countDown();
            else if (SystemClock.elapsedRealtime() < deadline) avatar.postDelayed(() -> pollAvatar(avatar, ready, deadline), 200);
        });
    }

    private static void inspectAvatar(ActivityScenario<MainActivity> scenario) throws Exception {
        scenario.onActivity(activity -> avatar(activity).loadUrl(AvatarView.PAGE + "?inspect"));
        awaitAvatar(scenario, "window.auraAvatar.ready", 15_000);
    }

    private static void fixtureToolCall(ActivityScenario<MainActivity> scenario, String... names) throws Exception {
        JSONObject arguments = new JSONObject().put("names", new JSONArray(List.of(names)));
        JSONObject function = new JSONObject().put("name", "set_avatar_expression").put("arguments", arguments.toString());
        JSONArray calls = new JSONArray().put(new JSONObject().put("id", "call_expression").put("function", function));
        JSONObject choice = new JSONObject().put("delta", new JSONObject().put("tool_calls", calls));
        JSONObject event = new JSONObject().put("choices", new JSONArray().put(choice));
        AuraChat.readEvents(bytes("data: " + event + "\ndata: [DONE]\n"), new CancellationSignal(), new AuraChat.Events() {
            @Override public void text(String delta) {}
            @Override public void expression(JSONArray allowed) {
                scenario.onActivity(activity -> avatar(activity).expression(allowed));
            }
        });
    }

    private static void awaitAvatar(ActivityScenario<MainActivity> scenario, String predicate) throws Exception {
        awaitAvatar(scenario, predicate, 2500);
    }

    private static void awaitAvatar(ActivityScenario<MainActivity> scenario, String predicate, long timeout) throws Exception {
        long deadline = SystemClock.elapsedRealtime() + timeout;
        do {
            CompletableFuture<String> result = new CompletableFuture<>();
            scenario.onActivity(activity -> avatar(activity).evaluateJavascript(
                "(() => { const p = window.auraAvatar?.inspectParameter; return !!p && (" + predicate + "); })()",
                result::complete));
            try {
                if ("true".equals(result.get(600, TimeUnit.MILLISECONDS))) return;
            } catch (TimeoutException navigation) {
                // WebView can discard a JavaScript callback when replacing the page.
            }
            SystemClock.sleep(25);
        } while (SystemClock.elapsedRealtime() < deadline);
        fail("Live2D parameters did not match " + predicate);
    }

    private static AvatarView avatar(MainActivity activity) {
        return find(activity.findViewById(android.R.id.content), AvatarView.class, null);
    }

    private static void writeWav(File file, short[] pcm) throws IOException {
        int sampleBytes = pcm.length * 2;
        int rate = NativeVoice.SAMPLE_RATE;
        ByteBuffer wav = ByteBuffer.allocate(sampleBytes + 44).order(ByteOrder.LITTLE_ENDIAN);
        wav.put(ascii("RIFF")).putInt(sampleBytes + 36).put(ascii("WAVEfmt ")).putInt(16);
        wav.putShort((short) 1).putShort((short) 1).putInt(rate).putInt(rate * 2).putShort((short) 2).putShort((short) 16);
        wav.put(ascii("data")).putInt(sampleBytes);
        for (short sample : pcm) wav.putShort(sample);
        try (FileOutputStream output = new FileOutputStream(file)) {
            output.write(wav.array());
        }
    }

    private static byte[] ascii(String text) {
        return text.getBytes(StandardCharsets.US_ASCII);
    }

    private static ByteArrayInputStream bytes(String text) {
        return new ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8));
    }

    private static <T extends View> T find(View root, Class<T> type, String text) {
        if (type.isInstance(root) && (text == null || root instanceof TextView value && text.contentEquals(value.getText()))) {
            return type.cast(root);
        }
        if (root instanceof ViewGroup group) {
            for (int i = 0; i < group.getChildCount(); i++) {
                T view = find(group.getChildAt(i), type, text);
                if (view != null) return view;
            }
        }
        return null;
    }

    private static <T extends View> T findDescription(View root, Class<T> type, String description) {
        if (type.isInstance(root) && description.contentEquals(root.getContentDescription() == null ? "" : root.getContentDescription())) {
            return type.cast(root);
        }
        if (root instanceof ViewGroup group) {
            for (int i = 0; i < group.getChildCount(); i++) {
                T view = findDescription(group.getChildAt(i), type, description);
                if (view != null) return view;
            }
        }
        return null;
    }
}
