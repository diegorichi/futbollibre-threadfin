package com.futbol.tv;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import android.os.Bundle;
import android.os.Build;
import android.os.Handler;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.Gravity;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.Toast;

import androidx.media3.common.MediaItem;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.hls.HlsMediaSource;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.ui.PlayerView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.URL;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Minimal remote-first TV UI: events -> sources -> preview -> fullscreen. */
public class MainActivity extends Activity {
    private static final String SERVICE_TYPE = "_futbol._tcp.";
    private static final int UDP_DISCOVERY_PORT = 45678;
    private static final float PIP_WIDTH_PERCENT = 0.15f;
    private static final int PIP_MARGIN_DP = 24;
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler();
    private FrameLayout root;
    private TvView screen;
    private PlayerView playerView;
    private PlayerView pipView;
    private ExoPlayer player;
    private ExoPlayer pipPlayer;
    private NsdManager nsd;
    private NsdManager.DiscoveryListener discovery;
    private String serverBase;
    private final List<Event> events = new ArrayList<>();
    private int state = TvView.SEARCHING;
    private int selectedEvent = 0;
    private int eventOffset = 0;
    private int selectedSource = 0;
    private int sourceOffset = 0;
    private int pipEvent = 0;
    private int pipEventOffset = 0;
    private int pipSource = 0;
    private int pipSourceOffset = 0;
    private int previewAction = 0;
    private final Map<String, Bitmap> logos = new HashMap<>();
    private String playerMessage = "";
    private final Runnable discoveryTimeout = () -> {
        if (serverBase == null && state == TvView.SEARCHING) {
            if (isEmulator()) connect("http://10.0.2.2:8080");
            else discoverByBroadcast();
        }
    };
    private final Runnable refreshTask = new Runnable() {
        @Override public void run() {
            if (serverBase != null && state != TvView.PLAYER && state != TvView.PREVIEW) loadEvents();
            main.postDelayed(this, 60000);
        }
    };

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        root = new FrameLayout(this);
        playerView = new PlayerView(this);
        playerView.setUseController(false);
        playerView.setVisibility(View.GONE);
        root.addView(playerView, new FrameLayout.LayoutParams(-1, -1));
        pipView = new PlayerView(this);
        pipView.setUseController(false);
        pipView.setVisibility(View.GONE);
        root.addView(pipView, new FrameLayout.LayoutParams(-1, -1));
        screen = new TvView(this);
        root.addView(screen, new FrameLayout.LayoutParams(-1, -1));
        setContentView(root);

        String explicit = getIntent().getStringExtra("server_url");
        if (explicit != null && !explicit.trim().isEmpty()) {
            connect(explicit);
        } else {
            discoverServer();
        }
    }

    private void discoverServer() {
        serverBase = null;
        state = TvView.SEARCHING;
        screen.invalidate();
        main.removeCallbacks(discoveryTimeout);
        main.postDelayed(discoveryTimeout, 6000);
        nsd = (NsdManager) getSystemService(NSD_SERVICE);
        discovery = new NsdManager.DiscoveryListener() {
            @Override public void onDiscoveryStarted(String serviceType) { }
            @Override public void onServiceFound(NsdServiceInfo info) {
                if (!SERVICE_TYPE.equals(info.getServiceType())) return;
                nsd.resolveService(info, new NsdManager.ResolveListener() {
                    @Override public void onResolveFailed(NsdServiceInfo serviceInfo, int errorCode) { }
                    @Override public void onServiceResolved(NsdServiceInfo serviceInfo) {
                        if (serverBase == null && serviceInfo.getHost() != null) {
                            connect("http://" + serviceInfo.getHost().getHostAddress() + ":" + serviceInfo.getPort());
                        }
                    }
                });
            }
            @Override public void onServiceLost(NsdServiceInfo serviceInfo) { }
            @Override public void onDiscoveryStopped(String serviceType) { }
            @Override public void onStartDiscoveryFailed(String serviceType, int errorCode) { stopDiscovery(); }
            @Override public void onStopDiscoveryFailed(String serviceType, int errorCode) { }
        };
        nsd.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, discovery);
    }

    private boolean isEmulator() {
        return Build.FINGERPRINT.startsWith("generic") || Build.MODEL.contains("Emulator") || Build.MODEL.contains("Android SDK");
    }

    private void discoverByBroadcast() {
        network.execute(() -> {
            try (DatagramSocket socket = new DatagramSocket()) {
                socket.setBroadcast(true);
                byte[] request = "FUTBOL_DISCOVER_V1".getBytes();
                socket.send(new DatagramPacket(request, request.length,
                        InetAddress.getByName("255.255.255.255"), UDP_DISCOVERY_PORT));
                socket.setSoTimeout(2500);
                byte[] buffer = new byte[512];
                DatagramPacket response = new DatagramPacket(buffer, buffer.length);
                socket.receive(response);
                JSONObject payload = new JSONObject(new String(response.getData(), 0, response.getLength()));
                String base = "http://" + response.getAddress().getHostAddress() + ":" + payload.optInt("port", 8080);
                main.post(() -> connect(base));
            } catch (Exception error) {
                main.post(() -> { state = TvView.ERROR; screen.invalidate(); });
            }
        });
    }

    private void connect(String base) {
        serverBase = base.replaceAll("/$", "");
        main.removeCallbacks(discoveryTimeout);
        stopDiscovery();
        main.removeCallbacks(refreshTask);
        main.postDelayed(refreshTask, 60000);
        loadEvents();
    }

    private void loadEvents() {
        state = TvView.SEARCHING;
        screen.invalidate();
        network.execute(() -> {
            try {
                String body = get(serverBase + "/api/v1/events");
                JSONArray array = new JSONObject(body).optJSONArray("events");
                List<Event> loaded = new ArrayList<>();
                if (array != null) {
                    for (int i = 0; i < array.length(); i++) loaded.add(Event.from(array.getJSONObject(i)));
                }
                main.post(() -> {
                    events.clear();
                    events.addAll(loaded);
                    state = TvView.EVENTS;
                    selectedEvent = Math.min(selectedEvent, Math.max(0, events.size() - 1));
                    eventOffset = 0;
                    screen.invalidate();
                    for (Event event : loaded) loadLogo(event);
                });
            } catch (Exception error) {
                main.post(() -> {
                    state = TvView.ERROR;
                    screen.invalidate();
                    Toast.makeText(this, "No se pudo cargar el servidor", Toast.LENGTH_SHORT).show();
                });
            }
        });
    }

    private void loadLogo(Event event) {
        if (event.logo.isEmpty() || logos.containsKey(event.logo)) return;
        network.execute(() -> {
            try (InputStream input = new URL(event.logo).openStream()) {
                Bitmap bitmap = BitmapFactory.decodeStream(input);
                if (bitmap != null) {
                    logos.put(event.logo, bitmap);
                    main.post(() -> screen.invalidate());
                }
            } catch (Exception ignored) { }
        });
    }

    private static String get(String address) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(address).openConnection();
        connection.setConnectTimeout(5000);
        connection.setReadTimeout(8000);
        connection.setRequestMethod("GET");
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(connection.getInputStream()))) {
            StringBuilder result = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) result.append(line);
            return result.toString();
        } finally { connection.disconnect(); }
    }

    private void preview(Source source) {
        state = TvView.PREVIEW;
        previewAction = 0;
        playerMessage = "Cargando preview...";
        setPlayerBounds(false);
        pipView.setVisibility(View.GONE);
        playerView.setUseController(false);
        playerView.setVisibility(View.VISIBLE);
        screen.invalidate();
        if (player != null) player.release();
        DefaultHttpDataSource.Factory http = new DefaultHttpDataSource.Factory()
                .setAllowCrossProtocolRedirects(true)
                .setUserAgent(source.userAgent == null ? "FutbolTV/0.1" : source.userAgent);
        player = new ExoPlayer.Builder(this).setMediaSourceFactory(new HlsMediaSource.Factory(http)).build();
        playerView.setPlayer(player);
        player.addListener(new Player.Listener() {
            @Override public void onPlaybackStateChanged(int playbackState) {
                if (playbackState == Player.STATE_READY) { playerMessage = "OK para pantalla completa"; screen.invalidate(); }
                if (playbackState == Player.STATE_ENDED) { playerMessage = "El stream terminó"; screen.invalidate(); }
            }
            @Override public void onPlayerError(PlaybackException error) {
                playerMessage = "No carga. Flechas para probar otra fuente";
                screen.invalidate();
            }
        });
        player.setMediaItem(MediaItem.fromUri(source.url));
        player.prepare();
        player.play();
    }

    private void openPipEventPicker() {
        if (events.size() < 2) {
            Toast.makeText(this, "No hay un segundo evento disponible", Toast.LENGTH_SHORT).show();
            return;
        }
        pipEvent = pipEvent == selectedEvent ? (selectedEvent + 1) % events.size() : pipEvent;
        pipEventOffset = Math.max(0, Math.min(Math.max(0, events.size() - 8), pipEvent - 5));
        state = TvView.PIP_EVENTS;
        screen.invalidate();
    }

    private void showPipSources() {
        if (events.get(pipEvent).sources.isEmpty()) return;
        pipSource = 0;
        pipSourceOffset = 0;
        state = TvView.PIP_SOURCES;
        screen.invalidate();
    }

    private void startPip(Source source) {
        if (player == null) return;
        pipPlayer = buildPlayer(source);
        pipPlayer.setVolume(0f);
        pipView.setPlayer(pipPlayer);
        pipView.setVisibility(View.VISIBLE);
        setDualBounds();
        pipPlayer.prepare();
        pipPlayer.play();
        state = TvView.DUAL;
        screen.invalidate();
    }

    private ExoPlayer buildPlayer(Source source) {
        DefaultHttpDataSource.Factory http = new DefaultHttpDataSource.Factory()
                .setAllowCrossProtocolRedirects(true)
                .setUserAgent(source.userAgent == null ? "FutbolTV/0.1" : source.userAgent);
        ExoPlayer result = new ExoPlayer.Builder(this)
                .setMediaSourceFactory(new HlsMediaSource.Factory(http)).build();
        result.setMediaItem(MediaItem.fromUri(source.url));
        return result;
    }

    private void setDualBounds() {
        FrameLayout.LayoutParams primary = new FrameLayout.LayoutParams(-1, -1);
        playerView.setLayoutParams(primary);
        int pipWidth = Math.round(getResources().getDisplayMetrics().widthPixels * PIP_WIDTH_PERCENT);
        int pipHeight = Math.round(pipWidth * 9f / 16f);
        FrameLayout.LayoutParams pip = new FrameLayout.LayoutParams(pipWidth, pipHeight);
        pip.gravity = Gravity.BOTTOM | Gravity.LEFT;
        pip.setMargins(dp(PIP_MARGIN_DP), 0, 0, dp(PIP_MARGIN_DP));
        pipView.setLayoutParams(pip);
    }

    private void swapPlayers() {
        ExoPlayer temporary = player;
        player = pipPlayer;
        pipPlayer = temporary;
        playerView.setPlayer(player);
        pipView.setPlayer(pipPlayer);
        player.setVolume(1f);
        pipPlayer.setVolume(0f);
        setDualBounds();
        screen.invalidate();
    }

    private void stopDiscovery() {
        if (nsd != null && discovery != null) {
            try { nsd.stopServiceDiscovery(discovery); } catch (Exception ignored) { }
            discovery = null;
        }
    }

    private void showSources() {
        if (events.isEmpty()) return;
        selectedSource = 0;
        sourceOffset = 0;
        state = TvView.SOURCES;
        playerView.setVisibility(View.GONE);
        screen.invalidate();
    }

    private void back() {
        if (state == TvView.DUAL) {
            if (pipPlayer != null) { pipPlayer.release(); pipPlayer = null; }
            pipView.setVisibility(View.GONE);
            state = TvView.PLAYER;
            setPlayerBounds(true);
        } else if (state == TvView.PLAYER) {
            state = TvView.PREVIEW;
            setPlayerBounds(false);
            playerView.setUseController(false);
            playerView.setVisibility(View.VISIBLE);
        } else if (state == TvView.PREVIEW) {
            state = TvView.SOURCES;
            playerView.setVisibility(View.GONE);
            if (player != null) player.stop();
        } else if (state == TvView.PIP_SOURCES) {
            state = TvView.PIP_EVENTS;
        } else if (state == TvView.PIP_EVENTS) {
            state = TvView.PREVIEW;
        } else if (state == TvView.SOURCES) {
            state = TvView.EVENTS;
        } else if (state == TvView.EVENTS || state == TvView.ERROR) {
            finish();
            return;
        }
        screen.invalidate();
    }

    private void setPlayerBounds(boolean fullscreen) {
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(
                fullscreen ? -1 : dp(640), fullscreen ? -1 : dp(360));
        params.gravity = Gravity.CENTER;
        playerView.setLayoutParams(params);
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private void tap(float y) {
        if (state == TvView.EVENTS && !events.isEmpty()) {
            int item = eventOffset + (int) ((y - 115) / 52);
            if (item >= 0 && item < events.size()) { selectedEvent = item; showSources(); }
        } else if (state == TvView.SOURCES && !events.isEmpty()) {
            int item = sourceOffset + (int) ((y - 145) / 48);
            if (item >= 0 && item < events.get(selectedEvent).sources.size()) { selectedSource = item; preview(events.get(selectedEvent).sources.get(item)); }
        } else if (state == TvView.PIP_EVENTS && !events.isEmpty()) {
            int item = pipEventOffset + (int) ((y - 115) / 52);
            if (item >= 0 && item < events.size()) { pipEvent = item; showPipSources(); }
        } else if (state == TvView.PIP_SOURCES && !events.isEmpty() && !events.get(pipEvent).sources.isEmpty()) {
            int item = pipSourceOffset + (int) ((y - 145) / 48);
            if (item >= 0 && item < events.get(pipEvent).sources.size()) { pipSource = item; startPip(events.get(pipEvent).sources.get(item)); }
        } else if (state == TvView.PREVIEW && player != null && player.getPlaybackState() == Player.STATE_READY) {
            state = TvView.PLAYER;
            setPlayerBounds(true);
            playerView.setUseController(true);
            if (player != null) {
                player.setPlayWhenReady(true);
                player.play();
            }
            playerView.showController();
            screen.invalidate();
        }
    }

    @Override public void onBackPressed() { back(); }

    @Override protected void onDestroy() {
        main.removeCallbacks(discoveryTimeout);
        main.removeCallbacks(refreshTask);
        stopDiscovery();
        if (player != null) player.release();
        if (pipPlayer != null) pipPlayer.release();
        network.shutdownNow();
        super.onDestroy();
    }

    private final class TvView extends View {
        static final int SEARCHING = 0, EVENTS = 1, SOURCES = 2, PREVIEW = 3, PLAYER = 4, ERROR = 5, PIP_EVENTS = 6, PIP_SOURCES = 7, DUAL = 8;
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final float density;
        TvView(Context context) { super(context); density = getResources().getDisplayMetrics().density; setFocusable(true); requestFocus(); }
        private float d(float value) { return value * density; }
        private void text(Canvas c, String value, float x, float y, float size, int color, boolean bold) {
            paint.setColor(color); paint.setTextSize(d(size)); paint.setTypeface(bold ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT); c.drawText(value, d(x), d(y), paint);
        }
        @Override protected void onDraw(Canvas c) {
            if (state == PREVIEW || state == PLAYER || state == DUAL) {
                if (state == PREVIEW) drawPreview(c);
                if (state == DUAL) drawDual(c);
                return;
            }
            c.drawColor(Color.rgb(7, 17, 31));
            if (state == SEARCHING) { text(c, "Buscando servidor...", 80, 90, 28, Color.WHITE, true); return; }
            if (state == ERROR) { text(c, "No se encontró el servidor", 80, 90, 28, Color.WHITE, true); text(c, "Back para salir · OK para reintentar", 80, 135, 18, Color.LTGRAY, false); return; }
            if (state == EVENTS) drawEvents(c, false);
            if (state == SOURCES) drawSources(c);
            if (state == PIP_EVENTS) drawEvents(c, true);
            if (state == PIP_SOURCES) drawPipSources(c);
        }
        private void header(Canvas c, String title) { text(c, title, 70, 62, 30, Color.WHITE, true); text(c, "Fútbol TV", 70, 96, 16, Color.rgb(94,234,212), true); }
        private void drawEvents(Canvas c, boolean forPip) {
            header(c, forPip ? "Elegí el segundo evento para PiP" : "Eventos");
            if (events.isEmpty()) { text(c, "No hay eventos disponibles", 80, 170, 22, Color.LTGRAY, false); return; }
            int offset = forPip ? pipEventOffset : eventOffset;
            int selected = forPip ? pipEvent : selectedEvent;
            for (int i = offset; i < Math.min(events.size(), offset + 8); i++) {
                Event e = events.get(i); float y = 145 + (i - offset) * 52;
                if (i == selected) { paint.setColor(Color.rgb(25, 57, 77)); c.drawRoundRect(d(55), d(y - 30), getWidth() - d(55), d(y + 14), d(8), d(8), paint); }
                drawLogo(c, e, 80, y - 24, 34);
                text(c, e.startsAt.length() >= 16 ? e.startsAt.substring(11, 16) : "--:--", 125, y, 20, Color.rgb(94,234,212), true);
                text(c, e.title, 215, y, 21, Color.WHITE, i == selected);
                text(c, e.sources.size() + " fuente" + (e.sources.size() == 1 ? "" : "s"), 780, y, 16, Color.LTGRAY, false);
            }
            text(c, forPip ? "El principal sigue reproduciendo · OK para ver sus fuentes" : "OK para seleccionar · Flechas para desplazarte", 70, 610, 16, Color.LTGRAY, false);
        }
        private void drawSources(Canvas c) {
            Event event = events.get(selectedEvent); header(c, event.title); text(c, "Elegí una fuente · Flechas para desplazarte", 70, 135, 18, Color.LTGRAY, false);
            if (event.sources.isEmpty()) { text(c, "No hay fuentes disponibles", 85, 205, 22, Color.LTGRAY, false); return; }
            int visibleEnd = Math.min(event.sources.size(), sourceOffset + 8);
            text(c, (sourceOffset + 1) + "–" + visibleEnd + " de " + event.sources.size(), getWidth() / density - 155, 135, 16, Color.LTGRAY, false);
            for (int i = sourceOffset; i < Math.min(event.sources.size(), sourceOffset + 8); i++) { float y = 170 + (i - sourceOffset) * 48; if (i == selectedSource) { paint.setColor(Color.rgb(25,57,77)); c.drawRoundRect(d(55),d(y-27),getWidth()-d(55),d(y+13),d(8),d(8),paint); } text(c, event.sources.get(i).name, 85, y, 20, Color.WHITE, i == selectedSource); }
        }
        private void drawPreview(Canvas c) { paint.setColor(Color.argb(220,7,17,31)); c.drawRect(0, getHeight()-d(125), getWidth(), getHeight(), paint); text(c, playerMessage, 60, getHeight()/density-92, 18, Color.WHITE, true); text(c, previewAction == 0 ? "[Ver en pantalla completa]" : "[Agregar segundo evento en PiP]", 60, getHeight()/density-55, 18, Color.rgb(94,234,212), true); text(c, "◀ ▶ elegir acción · ▲ ▼ cambiar fuente · OK confirmar · Back: fuentes", 60, getHeight()/density-18, 14, Color.LTGRAY, false); }
        private void drawDual(Canvas c) { text(c, "OK: enfocar PiP · Intercambiar: principal/PiP · Back: cerrar PiP", 35, getHeight()/density-18, 14, Color.WHITE, true); }
        private void drawPipSources(Canvas c) { c.drawColor(Color.rgb(7,17,31)); Event e=events.get(pipEvent); header(c,e.title); text(c,"Elegí la fuente para PiP · OK para reproducir muteado",70,135,18,Color.LTGRAY,false); for(int i=pipSourceOffset;i<Math.min(e.sources.size(),pipSourceOffset+8);i++){float y=170+(i-pipSourceOffset)*48;if(i==pipSource){paint.setColor(Color.rgb(25,57,77));c.drawRoundRect(d(55),d(y-27),getWidth()-d(55),d(y+13),d(8),d(8),paint);}text(c,e.sources.get(i).name,85,y,20,Color.WHITE,i==pipSource);} }
        private void drawLogo(Canvas c, Event event, float x, float y, float size) { Bitmap bitmap=logos.get(event.logo); if(bitmap!=null){c.drawBitmap(bitmap,null,new android.graphics.RectF(d(x),d(y),d(x+size),d(y+size)),paint);}else{paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(d(2));paint.setColor(Color.rgb(94,234,212));c.drawCircle(d(x+size/2),d(y+size/2),d(size/2-2),paint);paint.setStyle(Paint.Style.FILL);} }
        @Override public boolean onKeyDown(int keyCode, KeyEvent event) {
            if (keyCode == KeyEvent.KEYCODE_BACK) { back(); return true; }
            if (state == ERROR && (keyCode == KeyEvent.KEYCODE_DPAD_CENTER || keyCode == KeyEvent.KEYCODE_ENTER)) { discoverServer(); return true; }
            if (keyCode == KeyEvent.KEYCODE_DPAD_UP || keyCode == KeyEvent.KEYCODE_DPAD_DOWN) {
                int direction = keyCode == KeyEvent.KEYCODE_DPAD_UP ? -1 : 1;
                if (state == EVENTS && !events.isEmpty()) {
                    selectedEvent = Math.max(0, Math.min(events.size()-1, selectedEvent + direction));
                    eventOffset = Math.max(0, Math.min(Math.max(0, events.size() - 8), selectedEvent - 5));
                }
                if (state == SOURCES && !events.isEmpty() && !events.get(selectedEvent).sources.isEmpty()) {
                    selectedSource = Math.max(0, Math.min(events.get(selectedEvent).sources.size()-1, selectedSource + direction));
                    sourceOffset = Math.max(0, Math.min(Math.max(0, events.get(selectedEvent).sources.size() - 8), selectedSource - 4));
                }
                if (state == PREVIEW && !events.isEmpty() && !events.get(selectedEvent).sources.isEmpty()) { selectedSource = Math.max(0, Math.min(events.get(selectedEvent).sources.size()-1, selectedSource + direction)); preview(events.get(selectedEvent).sources.get(selectedSource)); }
                if (state == PIP_EVENTS && !events.isEmpty()) { pipEvent = Math.max(0, Math.min(events.size()-1, pipEvent + direction)); pipEventOffset = Math.max(0, Math.min(Math.max(0, events.size()-8), pipEvent-5)); }
                if (state == PIP_SOURCES && !events.get(pipEvent).sources.isEmpty()) { pipSource = Math.max(0, Math.min(events.get(pipEvent).sources.size()-1, pipSource + direction)); pipSourceOffset = Math.max(0, Math.min(Math.max(0, events.get(pipEvent).sources.size()-8), pipSource-4)); }
                invalidate(); return true;
            }
            if (keyCode == KeyEvent.KEYCODE_DPAD_LEFT || keyCode == KeyEvent.KEYCODE_DPAD_RIGHT) {
                if (state == PREVIEW) { previewAction = keyCode == KeyEvent.KEYCODE_DPAD_LEFT ? 0 : 1; invalidate(); return true; }
                if (state == DUAL && keyCode == KeyEvent.KEYCODE_DPAD_RIGHT && pipPlayer != null) { swapPlayers(); return true; }
            }
            if (keyCode == KeyEvent.KEYCODE_DPAD_CENTER || keyCode == KeyEvent.KEYCODE_ENTER) {
                if (state == EVENTS) showSources();
                else if (state == SOURCES && !events.get(selectedEvent).sources.isEmpty()) preview(events.get(selectedEvent).sources.get(selectedSource));
                else if (state == PREVIEW && player != null && player.getPlaybackState() == Player.STATE_READY) {
                    if (previewAction == 1) openPipEventPicker();
                    else { state = PLAYER; setPlayerBounds(true); playerView.setUseController(true); player.setPlayWhenReady(true); player.play(); playerView.setVisibility(View.VISIBLE); playerView.showController(); }
                }
                else if (state == PIP_EVENTS) showPipSources();
                else if (state == PIP_SOURCES && !events.get(pipEvent).sources.isEmpty()) startPip(events.get(pipEvent).sources.get(pipSource));
                invalidate(); return true;
            }
            return true;
        }
        @Override public boolean onTouchEvent(MotionEvent event) {
            if (event.getAction() == MotionEvent.ACTION_UP) { tap(event.getY() / density); return true; }
            return true;
        }
    }

    private static final class Event {
        final String title, startsAt, logo;
        final List<Source> sources = new ArrayList<>();
        Event(String title, String startsAt, String logo) { this.title = title; this.startsAt = startsAt; this.logo = logo; }
        static Event from(JSONObject json) throws Exception {
            Event event = new Event(json.optString("title", "Evento"), json.optString("starts_at", ""), json.optString("logo", ""));
            JSONArray sources = json.optJSONArray("sources");
            if (sources != null) for (int i = 0; i < sources.length(); i++) event.sources.add(Source.from(sources.getJSONObject(i)));
            return event;
        }
    }

    private static final class Source {
        final String name, url, userAgent;
        Source(String name, String url, String userAgent) { this.name = name; this.url = url; this.userAgent = userAgent; }
        static Source from(JSONObject json) { return new Source(json.optString("name", "Fuente"), json.optString("url", ""), json.optString("user_agent", null)); }
    }
}
