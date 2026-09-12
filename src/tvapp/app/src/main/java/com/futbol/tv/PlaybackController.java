package com.futbol.tv;

import android.content.Context;
import android.view.Gravity;
import android.view.View;
import android.widget.FrameLayout;

import androidx.media3.common.MediaItem;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.exoplayer.DefaultLoadControl;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.hls.HlsMediaSource;
import androidx.media3.ui.PlayerView;
import androidx.media3.ui.AspectRatioFrameLayout;

import com.futbol.tv.model.Source;

/** Owns all ExoPlayer instances and their visual bounds. */
public final class PlaybackController {
    public interface Listener { void onMessage(String message); }

    private static final float PIP_WIDTH_PERCENT = 0.15f;
    private static final int PIP_MARGIN_DP = 24;
    // Tolerates short interruptions without making startup excessively slow.
    private static final int MIN_BUFFER_MS = 50_000;
    private static final int MAX_BUFFER_MS = 120_000;
    private static final int BUFFER_FOR_PLAYBACK_MS = 2_500;
    private static final int BUFFER_AFTER_REBUFFER_MS = 5_000;
    private final Context context;
    private final PlayerView mainView;
    private final PlayerView pipView;
    private final Listener listener;
    private ExoPlayer primary;
    private ExoPlayer pip;

    public PlaybackController(Context context, PlayerView mainView, PlayerView pipView, Listener listener) {
        this.context = context;
        this.mainView = mainView;
        this.pipView = pipView;
        this.listener = listener;
        mainView.setResizeMode(AspectRatioFrameLayout.RESIZE_MODE_FIT);
        pipView.setResizeMode(AspectRatioFrameLayout.RESIZE_MODE_FIT);
    }

    public void preview(Source source) {
        releasePrimary();
        setPreviewBounds();
        pipView.setVisibility(View.GONE);
        mainView.setUseController(false);
        mainView.setVisibility(View.VISIBLE);
        primary = buildPlayer(source, false);
        mainView.setPlayer(primary);
        primary.prepare();
        primary.play();
    }

    public boolean isReady() {
        return primary != null && primary.getPlaybackState() == Player.STATE_READY;
    }

    public void enterFullscreen() {
        setFullscreenBounds();
        mainView.setUseController(true);
        mainView.setVisibility(View.VISIBLE);
        if (primary != null) {
            primary.setPlayWhenReady(true);
            primary.play();
        }
        mainView.showController();
    }

    public void switchPrimary(Source source) {
        releasePrimary();
        setFullscreenBounds();
        mainView.setUseController(true);
        mainView.setVisibility(View.VISIBLE);
        primary = buildPlayer(source, false);
        mainView.setPlayer(primary);
        primary.prepare();
        primary.play();
    }

    public void startPip(Source source) {
        if (primary == null) return;
        releasePip();
        pip = buildPlayer(source, true);
        pipView.setPlayer(pip);
        pipView.setVisibility(View.VISIBLE);
        setDualBounds();
        pip.prepare();
        pip.play();
    }

    public void closePip() {
        releasePip();
        pipView.setVisibility(View.GONE);
        setFullscreenBounds();
    }

    public void showPreview() {
        setPreviewBounds();
        mainView.setUseController(false);
        mainView.setVisibility(View.VISIBLE);
    }

    public void stopPrimary() {
        if (primary != null) primary.stop();
    }

    public void releaseAll() {
        releasePip();
        releasePrimary();
        pipView.setVisibility(View.GONE);
        mainView.setVisibility(View.GONE);
    }

    public void pauseAll() {
        if (primary != null) primary.pause();
        if (pip != null) pip.pause();
    }

    public void resumeAll() {
        if (primary != null) primary.play();
        if (pip != null) pip.play();
    }

    public void swap() {
        if (pip == null || primary == null) return;
        // Media3 puede conservar la superficie anterior si dos PlayerView se
        // intercambian directamente. Desacoplamos primero ambas vistas.
        mainView.setPlayer(null);
        pipView.setPlayer(null);
        ExoPlayer temporary = primary;
        primary = pip;
        pip = temporary;
        mainView.setPlayer(primary);
        pipView.setPlayer(pip);
        primary.setVolume(1f);
        pip.setVolume(0f);
        primary.play();
        pip.play();
        setDualBounds();
    }

    public void release() { releaseAll(); }

    public void onConfigurationChanged() {
        if (pip != null) setDualBounds();
        else if (primary != null && mainView.getVisibility() == View.VISIBLE) {
            // El video conserva su relación 16:9 dentro de la nueva pantalla,
            // incluso cuando el teléfono queda en modo vertical.
            if (mainView.getLayoutParams().width == -1) setFullscreenBounds();
            else setPreviewBounds();
        }
    }

    private ExoPlayer buildPlayer(Source source, boolean muted) {
        DefaultHttpDataSource.Factory http = new DefaultHttpDataSource.Factory()
                .setAllowCrossProtocolRedirects(true)
                .setUserAgent(source.userAgent == null ? "FutbolTV/0.1" : source.userAgent);
        DefaultLoadControl loadControl = new DefaultLoadControl.Builder()
                .setBufferDurationsMs(
                        MIN_BUFFER_MS,
                        MAX_BUFFER_MS,
                        BUFFER_FOR_PLAYBACK_MS,
                        BUFFER_AFTER_REBUFFER_MS)
                .build();
        ExoPlayer result = new ExoPlayer.Builder(context)
                .setLoadControl(loadControl)
                .setMediaSourceFactory(new HlsMediaSource.Factory(http)).build();
        result.setMediaItem(MediaItem.fromUri(source.url));
        result.setVolume(muted ? 0f : 1f);
        result.addListener(new Player.Listener() {
            @Override public void onPlaybackStateChanged(int playbackState) {
                if (playbackState == Player.STATE_READY) listener.onMessage("OK para pantalla completa");
                if (playbackState == Player.STATE_ENDED) listener.onMessage("El stream terminó");
            }
            @Override public void onPlayerError(PlaybackException error) {
                listener.onMessage("No carga. Flechas para probar otra fuente");
            }
        });
        return result;
    }

    private void releasePrimary() {
        if (primary != null) { primary.release(); primary = null; }
    }

    private void releasePip() {
        if (pip != null) { pip.release(); pip = null; }
    }

    private void setFullscreenBounds() {
        mainView.setLayoutParams(new FrameLayout.LayoutParams(-1, -1));
    }

    private void setPreviewBounds() {
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(dp(640), dp(360));
        params.gravity = Gravity.CENTER;
        mainView.setLayoutParams(params);
    }

    private void setDualBounds() {
        setFullscreenBounds();
        int pipWidth = Math.round(context.getResources().getDisplayMetrics().widthPixels * PIP_WIDTH_PERCENT);
        int pipHeight = Math.round(pipWidth * 9f / 16f);
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(pipWidth, pipHeight);
        params.gravity = Gravity.BOTTOM | Gravity.LEFT;
        params.setMargins(dp(PIP_MARGIN_DP), 0, 0, dp(PIP_MARGIN_DP));
        pipView.setLayoutParams(params);
    }

    private int dp(int value) {
        return (int) (value * context.getResources().getDisplayMetrics().density + 0.5f);
    }
}
