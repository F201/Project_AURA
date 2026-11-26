package com.aura.mobile;

import android.content.Context;
import android.net.Uri;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

final class VoiceModels {
    record Model(String name, long size, String sha256) {}
    static final Model TALKER = new Model("qwen-talker-0.6b-base-Q4_K_M.gguf", 628905056,
        "4b468ec7b1f62b90ef4ca316c0aa57deadfd54b2cf9651703ea753cedaf04226");
    static final Model CODEC = new Model("qwen-tokenizer-12hz-Q8_0.gguf", 291150624,
        "1883beeed99348fc35e23dd225e9082f93f6f8c109330a33d935baa8acdbfd94");
    private static final Model[] MODELS = {TALKER, CODEC};
    private static final String REPOSITORY = "https://huggingface.co/Serveurperso/Qwen3-TTS-GGUF/resolve/main/";
    final File directory;
    private final Context context;

    interface Progress { void update(String status); }

    VoiceModels(Context context) {
        this.context = context.getApplicationContext();
        directory = new File(context.getFilesDir(), "voice");
    }

    boolean ready() {
        return installed(TALKER) && installed(CODEC);
    }

    private boolean installed(Model model) {
        return new File(directory, model.name()).length() == model.size();
    }

    File embedding() throws IOException {
        ensureDirectory();
        File target = new File(directory, "aura-speaker.json");
        try (InputStream source = context.getAssets().open("aura-speaker.json")) {
            Files.copy(source, target.toPath(), StandardCopyOption.REPLACE_EXISTING);
        }
        return target;
    }

    void download(Progress progress) throws IOException {
        ensureDirectory();
        for (Model model : MODELS) {
            if (installed(model)) continue;
            HttpURLConnection connection = (HttpURLConnection) URI.create(REPOSITORY + model.name()).toURL().openConnection();
            connection.setConnectTimeout(15_000);
            connection.setReadTimeout(40_000);
            try {
                if (connection.getResponseCode() != 200) {
                    throw new IOException("Model download returned HTTP " + connection.getResponseCode());
                }
                try (InputStream input = connection.getInputStream()) {
                    install(model, input, progress);
                }
            } finally {
                connection.disconnect();
            }
        }
    }

    void importFile(Uri uri, String filename, Progress progress) throws IOException {
        ensureDirectory();
        try (InputStream source = context.getContentResolver().openInputStream(uri)) {
            if (source == null) throw new IOException("The selected file could not be opened.");
            if (filename.toLowerCase(Locale.ROOT).endsWith(".zip")) {
                try (ZipInputStream zip = new ZipInputStream(new BufferedInputStream(source))) {
                    for (ZipEntry entry; !ready() && (entry = zip.getNextEntry()) != null; zip.closeEntry()) {
                        if (entry.isDirectory()) continue;
                        Model model = identify(entry.getName());
                        if (model != null && !installed(model)) install(model, zip, progress);
                    }
                }
                if (!ready()) throw new IOException("The ZIP needs both AURA GGUF model files.");
            } else {
                Model model = identify(filename);
                if (model == null) throw new IOException("Choose the AURA backup ZIP or one of the two original GGUF files.");
                if (!installed(model)) install(model, source, progress);
            }
        }
    }

    static Model identify(String filename) {
        String basename = filename.replace('\\', '/');
        basename = basename.substring(basename.lastIndexOf('/') + 1);
        for (Model model : MODELS) if (model.name().equals(basename)) return model;
        return null;
    }

    private void ensureDirectory() throws IOException {
        Files.createDirectories(directory.toPath());
    }

    private void install(Model model, InputStream input, Progress progress) throws IOException {
        File partial = new File(directory, model.name() + ".part");
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
        try {
            try (FileOutputStream output = new FileOutputStream(partial)) {
                byte[] buffer = new byte[128 * 1024];
                long total = 0;
                long lastUpdate = -1;
                for (int count; (count = input.read(buffer)) != -1; ) {
                    if (Thread.currentThread().isInterrupted()) throw new IOException("Model setup was interrupted.");
                    total += count;
                    if (total > model.size()) throw new IOException("The model file is larger than expected.");
                    output.write(buffer, 0, count);
                    digest.update(buffer, 0, count);
                    long percent = total * 100 / model.size();
                    if (percent != lastUpdate) {
                        progress.update((model == TALKER ? "Installing voice model " : "Installing audio codec ") + percent + "%");
                        lastUpdate = percent;
                    }
                }
                if (total != model.size() || !hex(digest.digest()).equals(model.sha256())) {
                    throw new IOException("The model file failed its integrity check.");
                }
            }
            Files.move(partial.toPath(), new File(directory, model.name()).toPath(), StandardCopyOption.ATOMIC_MOVE);
        } finally {
            Files.deleteIfExists(partial.toPath());
        }
    }

    private static String hex(byte[] bytes) {
        StringBuilder result = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) {
            result.append(Character.forDigit((value & 0xff) >>> 4, 16));
            result.append(Character.forDigit(value & 0xf, 16));
        }
        return result.toString();
    }
}
