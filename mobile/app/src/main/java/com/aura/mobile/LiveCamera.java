package com.aura.mobile;

import android.graphics.Bitmap;
import android.view.ScaleGestureDetector;

import androidx.activity.ComponentActivity;
import androidx.camera.core.Camera;
import androidx.camera.core.CameraState;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.Preview;
import androidx.camera.core.ZoomState;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.camera.view.PreviewView.StreamState;
import androidx.lifecycle.LiveData;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.concurrent.ExecutionException;
import java.util.function.Consumer;

final class LiveCamera implements AutoCloseable {
    record State(boolean streaming, boolean canFlip, boolean front, float zoom) {}
    private final ComponentActivity owner;
    final PreviewView view;
    private final Consumer<State> stateChanged;
    private final Runnable failed;
    private ProcessCameraProvider provider;
    private Preview preview;
    private Camera activeCamera;
    private LiveData<CameraState> cameraStatus;
    private int generation;
    private boolean open;
    private boolean front, canFlip, streaming;
    private float zoom = 1f;

    LiveCamera(ComponentActivity owner, boolean startFront, Consumer<State> stateChanged, Runnable failed) {
        this.owner = owner;
        front = startFront;
        this.stateChanged = stateChanged;
        this.failed = failed;
        view = new PreviewView(owner);
        view.setImplementationMode(PreviewView.ImplementationMode.COMPATIBLE);
        view.setScaleType(PreviewView.ScaleType.FILL_CENTER);
        view.setContentDescription("Live camera preview");
        ScaleGestureDetector pinch = new ScaleGestureDetector(owner, new ScaleGestureDetector.SimpleOnScaleGestureListener() {
            @Override public boolean onScale(ScaleGestureDetector gesture) {
                return zoomBy(gesture.getScaleFactor());
            }
        });
        pinch.setQuickScaleEnabled(false);
        view.setOnTouchListener((target, motion) -> {
            pinch.onTouchEvent(motion);
            return true;
        });
        view.getPreviewStreamState().observe(owner, state -> {
            streaming = open && state == StreamState.STREAMING;
            publish();
        });
    }

    void open() {
        if (open) return;
        open = true;
        int request = ++generation;
        var pending = ProcessCameraProvider.getInstance(owner);
        pending.addListener(() -> {
            if (request != generation) return;
            try {
                provider = pending.get();
                boolean hasBack = provider.hasCamera(CameraSelector.DEFAULT_BACK_CAMERA);
                boolean hasFront = provider.hasCamera(CameraSelector.DEFAULT_FRONT_CAMERA);
                canFlip = hasBack && hasFront;
                if (!canFlip) front = !hasBack && hasFront;
                bind(request);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                close();
                failed.run();
            } catch (ExecutionException | RuntimeException | androidx.camera.core.CameraInfoUnavailableException error) {
                close();
                failed.run();
            }
        }, owner.getMainExecutor());
    }

    void flip() {
        if (!open || !streaming || !canFlip) return;
        front = !front;
        try {
            bind(++generation);
        } catch (RuntimeException failure) {
            close();
            failed.run();
        }
    }

    private void bind(int request) {
        streaming = false;
        zoom = 1f;
        publish();
        if (cameraStatus != null) cameraStatus.removeObservers(owner);
        if (preview != null) provider.unbind(preview);
        preview = new Preview.Builder().build();
        preview.setSurfaceProvider(view.getSurfaceProvider());
        CameraSelector selector = front ? CameraSelector.DEFAULT_FRONT_CAMERA : CameraSelector.DEFAULT_BACK_CAMERA;
        activeCamera = provider.bindToLifecycle(owner, selector, preview);
        cameraStatus = activeCamera.getCameraInfo().getCameraState();
        cameraStatus.observe(owner, state -> {
            if (open && request == generation && state.getError() != null) {
                close();
                failed.run();
            }
        });
    }

    private boolean zoomBy(float factor) {
        if (!streaming || activeCamera == null || !Float.isFinite(factor) || factor <= 0) return false;
        ZoomState range = activeCamera.getCameraInfo().getZoomState().getValue();
        if (range == null) return false;
        zoom = Math.max(range.getMinZoomRatio(), Math.min(range.getMaxZoomRatio(), zoom * factor));
        activeCamera.getCameraControl().setZoomRatio(zoom);
        publish();
        return true;
    }

    Bitmap frame() {
        return open && streaming ? view.getBitmap() : null;
    }

    static byte[] encode(Bitmap bitmap) throws IOException {
        try {
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            if (!bitmap.compress(Bitmap.CompressFormat.JPEG, 86, output)) throw new IOException("Couldn’t read the live camera frame.");
            return output.toByteArray();
        } finally {
            bitmap.recycle();
        }
    }

    @Override public void close() {
        open = false;
        ++generation;
        if (cameraStatus != null) cameraStatus.removeObservers(owner);
        if (provider != null && preview != null) provider.unbind(preview);
        activeCamera = null;
        cameraStatus = null;
        preview = null;
        streaming = false;
        canFlip = false;
        publish();
    }

    private void publish() {
        stateChanged.accept(new State(streaming, canFlip, front, zoom));
    }
}
