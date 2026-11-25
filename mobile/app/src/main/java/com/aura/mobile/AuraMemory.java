package com.aura.mobile;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteException;
import android.database.sqlite.SQLiteOpenHelper;
import android.net.Uri;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;

final class AuraMemory extends SQLiteOpenHelper {
    static final String FILE_NAME = "aura_memory.db";
    static final List<String> CATEGORIES = List.of("fact", "preference", "game", "joke", "schedule", "milestone");
    static final Snapshot EMPTY = new Snapshot("", List.of());
    private static final String MEMORY_COLUMNS = "id, category, content, importance, created_at";
    private static final long MAX_IMPORT_BYTES = 32L * 1024 * 1024;
    private final Context context;

    record Fact(String category, String content, int importance, double createdAt) {}
    record Snapshot(String userName, List<Fact> facts) {}
    record ImportResult(int added, boolean importedName) {}

    AuraMemory(Context context) {
        this(context, FILE_NAME);
    }

    AuraMemory(Context context, String filename) {
        super(context.getApplicationContext(), filename, null, 1);
        this.context = context.getApplicationContext();
        setWriteAheadLoggingEnabled(true);
    }

    @Override public void onCreate(SQLiteDatabase database) {
        database.execSQL("CREATE TABLE IF NOT EXISTS profile (key TEXT PRIMARY KEY, value TEXT NOT NULL)");
        database.execSQL("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT 'fact',
                content TEXT NOT NULL,
                importance INTEGER NOT NULL DEFAULT 5,
                created_at REAL NOT NULL
            )
            """);
    }

    @Override public void onUpgrade(SQLiteDatabase database, int oldVersion, int newVersion) {
        throw new IllegalStateException("Unsupported AURA memory database version.");
    }

    boolean remember(String fact, String category) {
        String content = fact.trim();
        if (content.isEmpty() || content.length() > 500) return false;
        Fact saved = new Fact(CATEGORIES.contains(category) ? category : "fact", content, 5,
            System.currentTimeMillis() / 1000.0);
        SQLiteDatabase database = getWritableDatabase();
        database.beginTransaction();
        try {
            insert(database, saved);
            database.setTransactionSuccessful();
            return true;
        } finally {
            database.endTransaction();
        }
    }

    Snapshot snapshot(int limit) {
        SQLiteDatabase database = getReadableDatabase();
        List<Fact> facts = new ArrayList<>();
        try (Cursor rows = database.rawQuery("SELECT " + MEMORY_COLUMNS
            + " FROM memories ORDER BY importance DESC, created_at DESC, id DESC LIMIT ?", new String[]{Integer.toString(limit)})) {
            while (rows.moveToNext()) facts.add(readFact(rows));
        }
        return new Snapshot(profileName(database), List.copyOf(facts));
    }

    void clear() {
        SQLiteDatabase database = getWritableDatabase();
        database.beginTransaction();
        try {
            database.delete("memories", null, null);
            database.delete("profile", "key = ?", new String[]{"user_name"});
            database.setTransactionSuccessful();
        } finally {
            database.endTransaction();
        }
    }

    ImportResult importDesktop(Uri uri) throws IOException {
        File temporary = File.createTempFile("aura-import-", ".db", context.getCacheDir());
        try {
            copy(uri, temporary);
            return importDesktop(temporary);
        } finally {
            SQLiteDatabase.deleteDatabase(temporary);
        }
    }

    ImportResult importDesktop(File source) throws IOException {
        int flags = SQLiteDatabase.OPEN_READONLY | SQLiteDatabase.NO_LOCALIZED_COLLATORS;
        try (SQLiteDatabase desktop = SQLiteDatabase.openDatabase(source.getAbsolutePath(), null, flags);
             Cursor rows = desktop.rawQuery("SELECT " + MEMORY_COLUMNS + " FROM memories ORDER BY id", null)) {
            String userName = profileName(desktop);
            SQLiteDatabase local = getWritableDatabase();
            local.beginTransaction();
            try {
                int added = 0;
                while (rows.moveToNext()) {
                    Fact fact = readFact(rows);
                    if (!fact.content().isBlank() && insert(local, fact)) added++;
                }
                boolean importedName = !userName.isBlank() && profileName(local).isBlank();
                if (importedName) {
                    ContentValues value = new ContentValues();
                    value.put("key", "user_name");
                    value.put("value", userName);
                    local.insertWithOnConflict("profile", null, value, SQLiteDatabase.CONFLICT_REPLACE);
                }
                local.setTransactionSuccessful();
                return new ImportResult(added, importedName);
            } finally {
                local.endTransaction();
            }
        } catch (SQLiteException invalid) {
            throw new IOException("Choose a desktop AURA memory database or SQLite export.", invalid);
        }
    }

    private void copy(Uri uri, File destination) throws IOException {
        try (InputStream data = context.getContentResolver().openInputStream(uri);
             FileOutputStream output = new FileOutputStream(destination)) {
            if (data == null) throw new IOException("The desktop memory file could not be opened.");
            byte[] buffer = new byte[64 * 1024];
            long total = 0;
            for (int count; (count = data.read(buffer)) != -1; ) {
                total += count;
                if (total > MAX_IMPORT_BYTES) throw new IOException("The desktop memory file is larger than 32 MB.");
                output.write(buffer, 0, count);
            }
        }
    }

    private static boolean insert(SQLiteDatabase database, Fact fact) {
        try (Cursor existing = database.rawQuery("SELECT id FROM memories WHERE lower(content) = lower(?) LIMIT 1",
            new String[]{fact.content()})) {
            if (existing.moveToFirst()) return false;
        }
        ContentValues values = new ContentValues();
        values.put("category", fact.category());
        values.put("content", fact.content());
        values.put("importance", fact.importance());
        values.put("created_at", fact.createdAt());
        database.insertOrThrow("memories", null, values);
        return true;
    }

    private static Fact readFact(Cursor rows) {
        return new Fact(rows.getString(1), rows.getString(2), rows.getInt(3), rows.getDouble(4));
    }

    private static String profileName(SQLiteDatabase database) {
        try (Cursor rows = database.rawQuery("SELECT value FROM profile WHERE key = 'user_name' LIMIT 1", null)) {
            return rows.moveToFirst() ? rows.getString(0) : "";
        }
    }
}
