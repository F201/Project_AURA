package com.aura.mobile;

import android.content.Context;
import android.graphics.Color;
import android.util.Log;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.webkit.WebViewAssetLoader;

import org.json.JSONArray;

final class AvatarView extends WebView {
    static final String PAGE = "https://appassets.androidplatform.net/avatar/mobile-avatar.html";
    private final ScaleGestureDetector pinch;
    private boolean pinching;

    AvatarView(Context context) {
        super(context);
        pinch = new ScaleGestureDetector(context, new ScaleGestureDetector.SimpleOnScaleGestureListener() {
            @Override public boolean onScale(ScaleGestureDetector gesture) {
                float factor = gesture.getScaleFactor();
                if (!Float.isFinite(factor) || factor <= 0) return false;
                evaluateJavascript("window.auraAvatar?.zoomBy(" + factor + ")", null);
                return true;
            }
        });
        pinch.setQuickScaleEnabled(false);
        setBackgroundColor(Color.TRANSPARENT);
        setContentDescription("AURA avatar");
        setVerticalScrollBarEnabled(false);
        getSettings().setJavaScriptEnabled(true);
        getSettings().setAllowFileAccess(false);
        getSettings().setAllowContentAccess(false);
        WebViewAssetLoader assets = new WebViewAssetLoader.Builder()
            .addPathHandler("/avatar/", new LocalAvatarAssets(context))
            .build();
        setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return true;
            }

            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                WebResourceResponse local = assets.shouldInterceptRequest(request.getUrl());
                if (local != null) return local;
                return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", null, null);
            }
        });
        loadUrl(PAGE);
    }

    @Override public boolean onTouchEvent(MotionEvent event) {
        if (event.getPointerCount() > 1 && !pinching) {
            MotionEvent cancel = MotionEvent.obtain(event);
            cancel.setAction(MotionEvent.ACTION_CANCEL);
            super.onTouchEvent(cancel);
            cancel.recycle();
            pinching = true;
        }
        pinch.onTouchEvent(event);
        if (pinching) {
            if (event.getActionMasked() == MotionEvent.ACTION_UP || event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
                pinching = false;
            }
            return true;
        }
        return super.onTouchEvent(event);
    }

    void mouth(float value) {
        evaluateJavascript("window.auraAvatar?.mouth(" + Math.max(0, Math.min(1, value)) + ")", null);
    }

    void expression(JSONArray names) {
        Log.d("AuraAvatar", "Expression " + names);
        evaluateJavascript("window.auraAvatar?.expression(" + names + ")", null);
    }

    private record LocalAvatarAssets(Context context) implements WebViewAssetLoader.PathHandler {
        @Override public WebResourceResponse handle(String path) {
            if (path.contains("..") || path.startsWith("/")) return null;
            int dot = path.lastIndexOf('.');
            String extension = dot < 0 ? "" : path.substring(dot + 1);
            String mime = switch (extension) {
                case "html" -> "text/html";
                case "js" -> "application/javascript";
                case "json" -> "application/json";
                case "css" -> "text/css";
                case "png" -> "image/png";
                case "jpg", "jpeg" -> "image/jpeg";
                default -> "application/octet-stream";
            };
            try {
                return new WebResourceResponse(mime, null, context.getAssets().open("avatar/" + path));
            } catch (java.io.IOException missing) {
                return null;
            }
        }
    }
}
