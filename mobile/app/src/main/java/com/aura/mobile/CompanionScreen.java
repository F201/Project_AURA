package com.aura.mobile;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.text.InputFilter;
import android.text.InputType;
import android.view.GestureDetector;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.Locale;

final class CompanionScreen extends FrameLayout {
    static final int INK = 0xfffff0e0;
    static final int MUTED = 0xffdbc3b6;
    static final int BACKGROUND = 0xff1c1416;
    static final int SURFACE = 0xff39292a;
    static final int GOLD = 0xfff1c891;
    private static final int ACTIVE = 0xff793b35;

    interface Actions {
        void settings();
        void camera();
        void flipCamera();
        void talk();
        void interrupt();
        void textMode();
        void send();
        void revealControls();
        void keepControlsVisible();
    }

    final AvatarView avatar;
    final EditText draft;
    final LinearLayout messages;
    final ScrollView history;
    private final TextView caption;
    private final TextView status;
    private final TextView cameraLabel;
    private final ImageButton flipCamera;
    private final FrameLayout cameraWindow;
    private final LinearLayout toolbar, stateRow, controls;
    private final Button cameraButton, talkButton, textButton, interrupt, send;
    private final LinearLayout textPanel;
    private final GestureDetector gestures;
    private final Actions actions;
    private boolean controlsHidden, flipAvailable, cameraStreaming;
    private boolean textVisible;
    private boolean keyboardOpen;

    CompanionScreen(Context context, LiveCamera camera, Actions actions) {
        super(context);
        this.actions = actions;
        gestures = new GestureDetector(context, new GestureDetector.SimpleOnGestureListener() {
            @Override public boolean onDown(MotionEvent event) { return true; }
            @Override public boolean onDoubleTap(MotionEvent event) {
                actions.revealControls();
                return true;
            }
        });
        setBackgroundColor(BACKGROUND);
        setFocusableInTouchMode(true);
        avatar = new AvatarView(context);
        addView(avatar, new LayoutParams(-1, -1));
        addScrim(Gravity.TOP, 124, GradientDrawable.Orientation.TOP_BOTTOM, 0xc51c1416);
        addScrim(Gravity.BOTTOM, 254, GradientDrawable.Orientation.BOTTOM_TOP, 0xf51c1416);

        FrameLayout safe = new FrameLayout(context);
        addView(safe, new LayoutParams(-1, -1));
        safe.setOnApplyWindowInsetsListener((view, insets) -> {
            var bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
            var ime = insets.getInsets(WindowInsets.Type.ime());
            safe.setPadding(bars.left, bars.top, bars.right, Math.max(bars.bottom, ime.bottom));
            keyboardOpen = insets.isVisible(WindowInsets.Type.ime());
            updateTextPanel();
            return insets;
        });

        toolbar = row(context);
        TextView title = label(context, "AURA", 20, INK);
        title.setTypeface(Typeface.create("serif", Typeface.BOLD));
        title.setLetterSpacing(.12f);
        toolbar.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        ImageButton settings = new ImageButton(context);
        settings.setImageDrawable(icon(context, R.drawable.ic_aura_settings, INK));
        settings.setContentDescription("Settings");
        settings.setBackground(ripple(0xdc39292a, 24));
        settings.setOnClickListener(v -> actions.settings());
        toolbar.addView(settings, new LinearLayout.LayoutParams(dp(48), dp(48)));
        LayoutParams toolbarSize = new LayoutParams(-1, dp(52), Gravity.TOP);
        toolbarSize.setMargins(dp(20), dp(8), dp(16), 0);
        safe.addView(toolbar, toolbarSize);

        cameraWindow = new FrameLayout(context);
        cameraWindow.setBackground(rounded(SURFACE, 16));
        cameraWindow.setClipToOutline(true);
        cameraWindow.addView(camera.view, new LayoutParams(-1, -1));
        cameraLabel = label(context, "Starting camera", 12, INK);
        cameraLabel.setPadding(dp(9), dp(5), dp(9), dp(5));
        cameraLabel.setBackground(rounded(BACKGROUND, 12));
        LayoutParams cameraLabelSize = new LayoutParams(-2, -2, Gravity.TOP | Gravity.START);
        cameraLabelSize.setMargins(dp(8), dp(8), 0, 0);
        cameraWindow.addView(cameraLabel, cameraLabelSize);
        flipCamera = new ImageButton(context);
        flipCamera.setImageDrawable(icon(context, R.drawable.ic_aura_flip_camera, INK));
        flipCamera.setBackground(ripple(0xe539292a, 24));
        flipCamera.setOnClickListener(v -> actions.flipCamera());
        LayoutParams flipSize = new LayoutParams(dp(48), dp(48), Gravity.BOTTOM | Gravity.END);
        flipSize.setMargins(0, 0, dp(6), dp(6));
        cameraWindow.addView(flipCamera, flipSize);
        flipCamera.setVisibility(GONE);
        LayoutParams cameraSize = new LayoutParams(dp(124), dp(164), Gravity.TOP | Gravity.END);
        cameraSize.setMargins(0, dp(70), dp(16), 0);
        safe.addView(cameraWindow, cameraSize);
        cameraWindow.setVisibility(GONE);

        LinearLayout bottom = column(context);
        bottom.setPadding(dp(16), 0, dp(16), dp(14));
        safe.addView(bottom, new LayoutParams(-1, -2, Gravity.BOTTOM));

        caption = label(context, "", 20, INK);
        caption.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        caption.setGravity(Gravity.CENTER);
        caption.setMaxLines(3);
        caption.setEllipsize(android.text.TextUtils.TruncateAt.END);
        caption.setShadowLayer(dp(5), 0, dp(1), Color.BLACK);
        caption.setPadding(dp(12), 0, dp(12), dp(6));
        caption.setVisibility(GONE);
        bottom.addView(caption, new LinearLayout.LayoutParams(-1, -2));

        stateRow = row(context);
        stateRow.setGravity(Gravity.CENTER);
        status = label(context, "", 14, MUTED);
        status.setGravity(Gravity.CENTER);
        status.setAccessibilityLiveRegion(ACCESSIBILITY_LIVE_REGION_POLITE);
        stateRow.addView(status, new LinearLayout.LayoutParams(0, -2, 1));
        interrupt = button(context, "Interrupt", SURFACE, INK, v -> actions.interrupt());
        stateRow.addView(interrupt, new LinearLayout.LayoutParams(-2, dp(48)));
        interrupt.setVisibility(GONE);
        LinearLayout.LayoutParams stateSize = new LinearLayout.LayoutParams(-1, -2);
        stateSize.bottomMargin = dp(10);
        bottom.addView(stateRow, stateSize);

        textPanel = column(context);
        textPanel.setPadding(dp(12), dp(8), dp(12), dp(10));
        textPanel.setBackground(rounded(0xf42b1d1e, 16));
        history = new ScrollView(context);
        history.setVerticalScrollBarEnabled(false);
        messages = column(context);
        history.addView(messages, new ScrollView.LayoutParams(-1, -2));
        textPanel.addView(history, new LinearLayout.LayoutParams(-1, dp(188)));

        LinearLayout composer = row(context);
        draft = new EditText(context);
        draft.setHint("Message AURA");
        draft.setTextColor(INK);
        draft.setHintTextColor(MUTED);
        draft.setTextSize(16);
        draft.setFilters(new InputFilter[]{new InputFilter.LengthFilter(4000)});
        draft.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        draft.setMaxLines(3);
        draft.setPadding(dp(12), dp(8), dp(12), dp(8));
        draft.setBackground(rounded(SURFACE, 12));
        composer.addView(draft, new LinearLayout.LayoutParams(0, -2, 1));
        send = button(context, "Send", GOLD, BACKGROUND, v -> actions.send());
        LinearLayout.LayoutParams sendSize = new LinearLayout.LayoutParams(-2, dp(48));
        sendSize.leftMargin = dp(8);
        composer.addView(send, sendSize);
        textPanel.addView(composer, new LinearLayout.LayoutParams(-1, -2));
        LinearLayout.LayoutParams textSize = new LinearLayout.LayoutParams(-1, -2);
        textSize.bottomMargin = dp(10);
        bottom.addView(textPanel, textSize);

        controls = row(context);
        cameraButton = button(context, "Camera", SURFACE, INK, v -> actions.camera());
        decorate(cameraButton, R.drawable.ic_aura_camera, INK);
        controls.addView(cameraButton, new LinearLayout.LayoutParams(-2, dp(56)));
        talkButton = button(context, "Talk", GOLD, BACKGROUND, v -> actions.talk());
        decorate(talkButton, R.drawable.ic_aura_mic, BACKGROUND);
        LinearLayout.LayoutParams talkSize = new LinearLayout.LayoutParams(0, dp(56), 1);
        talkSize.setMargins(dp(8), 0, dp(8), 0);
        controls.addView(talkButton, talkSize);
        textButton = button(context, "Type", SURFACE, INK, v -> actions.textMode());
        decorate(textButton, R.drawable.ic_aura_keyboard, INK);
        controls.addView(textButton, new LinearLayout.LayoutParams(-2, dp(56)));
        bottom.addView(controls, new LinearLayout.LayoutParams(-1, -2));
        updateTextPanel();
    }

    @Override public boolean dispatchTouchEvent(MotionEvent event) {
        boolean wasHidden = controlsHidden;
        if (event.getActionMasked() == MotionEvent.ACTION_UP && !wasHidden) actions.keepControlsVisible();
        gestures.onTouchEvent(event);
        if (wasHidden && !controlsHidden) return true;
        return super.dispatchTouchEvent(event);
    }

    void setControlsHidden(boolean hidden) {
        controlsHidden = hidden;
        int visibility = hidden ? INVISIBLE : VISIBLE;
        toolbar.setVisibility(visibility);
        stateRow.setVisibility(visibility);
        controls.setVisibility(visibility);
        updateFlipButton();
    }

    boolean controlsHidden() {
        return controlsHidden;
    }

    void setTalk(boolean mode) {
        talkButton.setText(mode ? "End talk" : "Talk");
        talkButton.setTextColor(mode ? INK : BACKGROUND);
        talkButton.setBackground(ripple(mode ? ACTIVE : GOLD, 24));
        decorate(talkButton, mode ? R.drawable.ic_aura_stop : R.drawable.ic_aura_mic, mode ? INK : BACKGROUND);
    }

    void setBusy(boolean busy, boolean inTalk) {
        send.setText(busy ? "Stop" : "Send");
        interrupt.setVisibility(busy && inTalk ? VISIBLE : GONE);
    }

    void setCamera(boolean open, LiveCamera.State state) {
        cameraWindow.setVisibility(open ? VISIBLE : GONE);
        String lens = state.front() ? "Front camera" : "Rear camera";
        if (Math.abs(state.zoom() - 1f) >= 0.05f) lens += String.format(Locale.getDefault(), " %.1f×", state.zoom());
        cameraLabel.setText(state.streaming() ? lens : "Starting camera");
        cameraButton.setBackground(ripple(open ? ACTIVE : SURFACE, 24));
        cameraButton.setContentDescription(open ? "Close camera" : "Open camera");
        flipAvailable = open && state.canFlip();
        cameraStreaming = state.streaming();
        updateFlipButton();
        flipCamera.setContentDescription(state.front() ? "Switch to rear camera" : "Switch to front camera");
    }

    private void updateFlipButton() {
        flipCamera.setVisibility(flipAvailable && !controlsHidden ? VISIBLE : GONE);
        flipCamera.setEnabled(cameraStreaming);
    }

    void setTextMode(boolean visible) {
        textVisible = visible;
        textButton.setBackground(ripple(visible ? ACTIVE : SURFACE, 24));
        textButton.setContentDescription(visible ? "Close text chat" : "Open text chat");
        updateTextPanel();
    }

    boolean textMode() {
        return textVisible;
    }

    void setStatus(String text) {
        status.setText(text);
        status.setVisibility(text.isEmpty() ? GONE : VISIBLE);
    }

    void setCaption(String text) {
        caption.setText(text);
        updateTextPanel();
    }

    TextView addMessage(boolean user, String text) {
        TextView line = label(getContext(), text, 16, user ? BACKGROUND : INK);
        line.setTextIsSelectable(true);
        line.setBackground(rounded(user ? GOLD : SURFACE, 14));
        line.setPadding(dp(12), dp(7), dp(12), dp(7));
        LinearLayout.LayoutParams size = new LinearLayout.LayoutParams(-2, -2);
        size.topMargin = dp(5);
        size.gravity = user ? Gravity.END : Gravity.START;
        line.setMaxWidth(getResources().getDisplayMetrics().widthPixels - dp(94));
        messages.addView(line, size);
        scrollToLatest();
        return line;
    }

    void scrollToLatest() {
        if (textVisible) history.post(() -> history.fullScroll(FOCUS_DOWN));
    }

    private void updateTextPanel() {
        textPanel.setVisibility(textVisible ? VISIBLE : GONE);
        history.setVisibility(keyboardOpen ? GONE : VISIBLE);
        caption.setVisibility(textVisible || caption.length() == 0 ? GONE : VISIBLE);
    }

    private void addScrim(int gravity, int height, GradientDrawable.Orientation orientation, int color) {
        View shade = new View(getContext());
        shade.setBackground(new GradientDrawable(orientation, new int[]{color, Color.TRANSPARENT}));
        shade.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
        addView(shade, new LayoutParams(-1, dp(height), gravity));
    }

    private void decorate(Button button, int res, int color) {
        button.setCompoundDrawablesRelativeWithIntrinsicBounds(icon(getContext(), res, color), null, null, null);
        button.setCompoundDrawablePadding(dp(6));
    }

    private static Drawable icon(Context context, int res, int color) {
        Drawable drawable = context.getDrawable(res).mutate();
        drawable.setTint(color);
        return drawable;
    }

    static LinearLayout column(Context context) {
        LinearLayout column = new LinearLayout(context);
        column.setOrientation(LinearLayout.VERTICAL);
        return column;
    }

    private static LinearLayout row(Context context) {
        LinearLayout row = new LinearLayout(context);
        row.setGravity(Gravity.CENTER_VERTICAL);
        return row;
    }

    static TextView label(Context context, String text, int size, int color) {
        TextView label = new TextView(context);
        label.setText(text);
        label.setTextSize(size);
        label.setTextColor(color);
        return label;
    }

    static Button button(Context context, String text, int fill, int ink, OnClickListener click) {
        Button button = new Button(context);
        button.setText(text);
        button.setAllCaps(false);
        button.setTextColor(ink);
        button.setTextSize(14);
        button.setBackground(ripple(fill, 24));
        int padding = Math.round(12 * context.getResources().getDisplayMetrics().density);
        button.setPadding(padding, 0, padding, 0);
        button.setMinHeight(4 * padding);
        button.setMinimumHeight(4 * padding);
        button.setOnClickListener(click);
        return button;
    }

    private static GradientDrawable rounded(int color, int radius) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(color);
        shape.setCornerRadius(radius * android.content.res.Resources.getSystem().getDisplayMetrics().density);
        return shape;
    }

    private static RippleDrawable ripple(int color, int radius) {
        return new RippleDrawable(ColorStateList.valueOf(0x23ffffff), rounded(color, radius), null);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
