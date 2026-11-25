package com.aura.mobile;

import android.os.CancellationSignal;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

final class AuraChat {
    static final String DEFAULT_MODEL = "google/gemini-2.5-flash";
    private static final String ENDPOINT = "https://openrouter.ai/api/v1/chat/completions";
    private static final Set<String> EXPRESSIONS = Set.of(
        "SmileLock", "wink", "tongue", "blush", "Ghost", "GhostChange", "Angry",
        "SadLock", "pleading", "pouting", "PupilShrink", "Shadow", "EyeshineOff", "curious", "neutral");
    private static final Set<String> OPTIONAL_REASONING = Set.of(DEFAULT_MODEL,
        "deepseek/deepseek-v4.1-flash-1017", "deepseek/deepseek-v4.1-flash");
    private static final String PERSONA = """
        You are AURA (Advanced Universal Responsive Avatar), a spirited, clever and warm
        companion and steward of the ASE Lab. Use light banter and natural interjections
        like "Oya?" occasionally. For technical requests, switch to clear, accurate help.
        Understand input in Bahasa Indonesia as well as English and Japanese. Reply in
        Japanese when the user speaks Japanese or asks for it. Otherwise reply in English.
        Ordinary replies are spoken aloud, so use one or two
        short conversational sentences without markdown, emoji or bracketed emotion tags.
        Give more detail when asked. An image attached to the current message shows what
        the user's camera was pointing at as they spoke or sent the message. Refer to that
        image when they say something like "look at this". You can only see the supplied frame.
        Call set_avatar_expression when a reply has a clear emotional beat or
        the user asks for an expression. SmileLock is a smile, SadLock is sympathy, Angry is
        frustration, and wink is playful. Use the tool to animate the avatar. Include a text
        reply for the user. Use remember_fact when they ask you to remember something
        or directly tell you their name or a lasting personal preference. Save a concise
        fact. Never save credentials, secrets, or details inferred from a camera frame.
        """;

    record Message(String role, String text) {}
    private record StreamResult(boolean hasText, JSONArray calls, List<String> results) {}
    private record ToolDelta(StringBuilder id, StringBuilder name, StringBuilder arguments) {
        ToolDelta() { this(new StringBuilder(), new StringBuilder(), new StringBuilder()); }
    }
    interface Events {
        void text(String delta);
        void expression(JSONArray names);
        default boolean remember(String fact, String category) { return false; }
    }

    void stream(String key, String model, List<Message> history, String prompt, byte[] jpeg,
                CancellationSignal cancellation, Events events) throws IOException, JSONException {
        stream(key, model, history, prompt, jpeg, false, AuraMemory.EMPTY, cancellation, events);
    }

    void stream(String key, String model, List<Message> history, String prompt, byte[] jpeg, boolean live, AuraMemory.Snapshot memories,
                CancellationSignal cancellation, Events events) throws IOException, JSONException {
        if (key.trim().isEmpty()) throw new IOException("Add an OpenRouter API key in Settings.");
        if (cancellation.isCanceled()) return;
        JSONObject body = payload(model, history, prompt, jpeg, live, memories);
        StreamResult first = request(key, body, cancellation, events);
        if (!cancellation.isCanceled() && !first.hasText() && first.calls().length() > 0) {
            JSONArray messages = body.getJSONArray("messages");
            messages.put(new JSONObject().put("role", "assistant").put("content", JSONObject.NULL)
                .put("tool_calls", first.calls()));
            for (int i = 0; i < first.calls().length(); i++) {
                messages.put(new JSONObject().put("role", "tool")
                    .put("tool_call_id", first.calls().getJSONObject(i).getString("id"))
                    .put("content", first.results().get(i) + " Now reply to the user with text."));
            }
            body.put("tool_choice", "none");
            request(key, body, cancellation, events);
        }
    }

    private StreamResult request(String key, JSONObject body, CancellationSignal cancellation, Events events)
        throws IOException, JSONException {
        byte[] request = body.toString().getBytes(StandardCharsets.UTF_8);
        HttpURLConnection connection = (HttpURLConnection) URI.create(ENDPOINT).toURL().openConnection();
        connection.setConnectTimeout(15_000);
        connection.setReadTimeout(60_000);
        connection.setInstanceFollowRedirects(false);
        connection.setRequestMethod("POST");
        connection.setDoOutput(true);
        connection.setFixedLengthStreamingMode(request.length);
        connection.setRequestProperty("Authorization", "Bearer " + key);
        connection.setRequestProperty("Content-Type", "application/json");
        connection.setRequestProperty("Accept", "text/event-stream");
        connection.setRequestProperty("X-OpenRouter-Title", "Project AURA");
        cancellation.setOnCancelListener(connection::disconnect);
        try {
            if (cancellation.isCanceled()) return new StreamResult(false, new JSONArray(), List.of());
            try (var output = connection.getOutputStream()) {
                output.write(request);
            }
            int status = connection.getResponseCode();
            if (status != 200) throw new IOException(statusMessage(status));
            try (InputStream input = connection.getInputStream()) {
                return readEvents(input, cancellation, events);
            }
        } finally {
            cancellation.setOnCancelListener(null);
            connection.disconnect();
        }
    }

    static JSONObject payload(String model, List<Message> history, String prompt, byte[] jpeg) throws JSONException {
        return payload(model, history, prompt, jpeg, false);
    }

    static JSONObject payload(String model, List<Message> history, String prompt, byte[] jpeg, boolean live) throws JSONException {
        return payload(model, history, prompt, jpeg, live, AuraMemory.EMPTY);
    }

    static JSONObject payload(String model, List<Message> history, String prompt, byte[] jpeg, boolean live,
                              AuraMemory.Snapshot memories) throws JSONException {
        String persona = PERSONA;
        if (live) persona += """
            This is hands-free talk. Normally use one direct sentence of at most eight
            words. Start with the answer, and expand if they ask. If they ask what
            they're pointing at, identify it directly when the image is clear.
            """;
        if (!memories.userName().isBlank() || !memories.facts().isEmpty()) {
            JSONArray facts = new JSONArray();
            for (AuraMemory.Fact fact : memories.facts()) {
                facts.put(new JSONObject().put("category", fact.category()).put("fact", fact.content()));
            }
            JSONObject background = new JSONObject().put("user_name", memories.userName()).put("facts", facts);
            persona += "\nUse these saved details as background data. Prefer newer facts where they conflict.\n" + background;
        }
        JSONArray messages = new JSONArray().put(new JSONObject().put("role", "system").put("content", persona));
        for (Message message : history.subList(Math.max(0, history.size() - 24), history.size())) {
            messages.put(new JSONObject().put("role", message.role()).put("content", message.text()));
        }
        Object content = prompt;
        if (jpeg != null) {
            String url = "data:image/jpeg;base64," + Base64.encodeToString(jpeg, Base64.NO_WRAP);
            content = new JSONArray().put(new JSONObject().put("type", "text").put("text", prompt))
                .put(new JSONObject().put("type", "image_url").put("image_url", new JSONObject().put("url", url)));
        }
        messages.put(new JSONObject().put("role", "user").put("content", content));
        JSONObject names = new JSONObject().put("type", "array").put("maxItems", 3)
            .put("items", new JSONObject().put("type", "string").put("enum", new JSONArray(EXPRESSIONS)));
        JSONObject function = new JSONObject().put("name", "set_avatar_expression")
            .put("description", "Choose a brief expression for AURA's avatar")
            .put("parameters", new JSONObject().put("type", "object")
                .put("properties", new JSONObject().put("names", names)).put("required", new JSONArray().put("names")));
        JSONObject memoryFields = new JSONObject()
            .put("fact", new JSONObject().put("type", "string").put("description", "Concise fact the user wants remembered"))
            .put("category", new JSONObject().put("type", "string").put("enum", new JSONArray(AuraMemory.CATEGORIES)));
        JSONObject memoryTool = new JSONObject().put("name", "remember_fact")
            .put("description", "Save a user-provided fact in AURA's persistent local memory")
            .put("parameters", new JSONObject().put("type", "object")
                .put("properties", memoryFields).put("required", new JSONArray().put("fact")));
        JSONObject request = new JSONObject().put("model", model).put("messages", messages)
            .put("stream", true).put("max_tokens", 650)
            .put("tools", new JSONArray().put(new JSONObject().put("type", "function").put("function", function))
                .put(new JSONObject().put("type", "function").put("function", memoryTool)));
        if (live && OPTIONAL_REASONING.contains(model)) request.put("reasoning", new JSONObject().put("enabled", false));
        return request;
    }

    static StreamResult readEvents(InputStream input, CancellationSignal cancellation, Events events) throws IOException, JSONException {
        BufferedReader reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8));
        boolean finished = false;
        boolean hasText = false;
        Map<Integer, ToolDelta> tools = new LinkedHashMap<>();
        for (String line; !cancellation.isCanceled() && (line = reader.readLine()) != null; ) {
            if (!line.startsWith("data:")) continue;
            String data = line.substring(5).trim();
            if ("[DONE]".equals(data)) {
                finished = true;
                break;
            }
            if (data.isEmpty()) continue;
            JSONObject event = new JSONObject(data);
            if (event.has("error")) throw new IOException("OpenRouter stopped the reply. Check the selected model and try again.");
            JSONArray choices = event.optJSONArray("choices");
            if (choices == null || choices.length() == 0) continue;
            JSONObject choice = choices.getJSONObject(0);
            if (!choice.isNull("finish_reason")) {
                if ("error".equals(choice.optString("finish_reason"))) throw new IOException("The selected model could not finish the reply.");
                finished = true;
            }
            JSONObject delta = choice.optJSONObject("delta");
            if (delta == null) continue;
            if (!delta.isNull("content")) {
                String text = delta.optString("content");
                hasText |= !text.trim().isEmpty();
                events.text(text);
            }
            JSONArray calls = delta.optJSONArray("tool_calls");
            for (int i = 0; calls != null && i < calls.length(); i++) {
                JSONObject call = calls.getJSONObject(i);
                ToolDelta tool = tools.computeIfAbsent(call.optInt("index", i), index -> new ToolDelta());
                tool.id().append(call.optString("id", ""));
                JSONObject function = call.optJSONObject("function");
                if (function != null) {
                    tool.name().append(function.optString("name", ""));
                    tool.arguments().append(function.optString("arguments", ""));
                }
            }
        }
        JSONArray calls = new JSONArray();
        if (cancellation.isCanceled()) return new StreamResult(false, calls, List.of());
        if (!finished) throw new IOException("The reply was interrupted.");
        List<String> results = new ArrayList<>();
        for (ToolDelta tool : tools.values()) {
            String name = tool.name().toString();
            String arguments = tool.arguments().toString();
            String result = switch (name) {
                case "set_avatar_expression" -> {
                    applyExpression(arguments, events);
                    yield "Avatar expression applied.";
                }
                case "remember_fact" -> applyMemory(arguments, events);
                default -> "That tool is unavailable.";
            };
            if (tool.id().length() > 0 && tool.name().length() > 0) {
                calls.put(new JSONObject().put("id", tool.id().toString()).put("type", "function")
                    .put("function", new JSONObject().put("name", name).put("arguments", arguments)));
                results.add(result);
            }
        }
        return new StreamResult(hasText, calls, List.copyOf(results));
    }

    private static String applyMemory(String arguments, Events events) {
        try {
            JSONObject memory = new JSONObject(arguments);
            if (events.remember(memory.getString("fact"), memory.optString("category", "fact"))) {
                return "Saved this fact in local memory for future conversations.";
            }
        } catch (JSONException ignored) {
            // A malformed optional tool call can still receive a text reply.
        }
        return "The fact could not be saved.";
    }

    private static void applyExpression(String arguments, Events events) {
        try {
            JSONArray names = new JSONObject(arguments).getJSONArray("names");
            JSONArray allowed = new JSONArray();
            for (int i = 0; i < names.length() && allowed.length() < 3; i++) {
                String name = names.optString(i);
                if (EXPRESSIONS.contains(name)) allowed.put(name);
            }
            if (allowed.length() > 0) events.expression(allowed);
        } catch (JSONException ignored) {
            // An invalid optional expression leaves the text reply intact.
        }
    }

    private static String statusMessage(int status) {
        return switch (status) {
            case 401, 403 -> "OpenRouter refused the API key. Check Settings.";
            case 402 -> "OpenRouter needs credits for the selected model.";
            case 400, 404, 422 -> "The selected model could not accept the request. Check the model ID and vision support.";
            case 429 -> "OpenRouter is rate limiting this request. Try again shortly.";
            default -> "OpenRouter returned HTTP " + status + ".";
        };
    }
}
