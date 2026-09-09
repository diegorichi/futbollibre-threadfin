package com.futbol.tv;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import android.os.Bundle;
import android.os.Build;
import android.os.Handler;
import android.view.KeyEvent;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.Toast;

import androidx.media3.ui.PlayerView;

import org.json.JSONObject;

import com.futbol.tv.model.Event;
import com.futbol.tv.model.Source;

import java.io.InputStream;
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
public class MainActivity extends Activity implements TvScreenView.Host {
    private static final String SERVICE_TYPE = "_futbol._tcp.";
    private static final int UDP_DISCOVERY_PORT = 45678;
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private final ServerClient serverClient = new ServerClient();
    private final Handler main = new Handler();
    private FrameLayout root;
    private TvScreenView screen;
    private PlayerView playerView;
    private PlayerView pipView;
    private PlaybackController playback;
    private NsdManager nsd;
    private NsdManager.DiscoveryListener discovery;
    private String serverBase;
    private final List<Event> events = new ArrayList<>();
    private int state = TvScreenView.SEARCHING;
    private int selectedEvent = 0;
    private int eventOffset = 0;
    private int selectedSource = 0;
    private int sourceOffset = 0;
    private int pipEvent = 0;
    private int pipEventOffset = 0;
    private int pipSource = 0;
    private int pipSourceOffset = 0;
    private int previewAction = 0;
    private boolean resumePlaybackOnStart;
    private final Map<String, Bitmap> logos = new HashMap<>();
    private String playerMessage = "";
    private final Runnable discoveryTimeout = () -> {
        if (serverBase == null && state == TvScreenView.SEARCHING) {
            if (isEmulator()) connect("http://10.0.2.2:8080");
            else discoverByBroadcast();
        }
    };
    private final Runnable refreshTask = new Runnable() {
        @Override public void run() {
            // Nunca cambiar la pantalla mientras se reproduce un stream. El
            // refresco del catálogo queda limitado a la pantalla de eventos.
            if (serverBase != null && state == TvScreenView.EVENTS) loadEvents(false);
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
        playback = new PlaybackController(this, playerView, pipView, message -> {
            playerMessage = message;
            main.post(() -> screen.invalidate());
        });
        screen = new TvScreenView(this, this);
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
        state = TvScreenView.SEARCHING;
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
                main.post(() -> { state = TvScreenView.ERROR; screen.invalidate(); });
            }
        });
    }

    private void connect(String base) {
        serverBase = base.replaceAll("/$", "");
        main.removeCallbacks(discoveryTimeout);
        stopDiscovery();
        main.removeCallbacks(refreshTask);
        main.postDelayed(refreshTask, 60000);
        loadEvents(true);
    }

    private void loadEvents(boolean showLoading) {
        final int requestedFromState = state;
        if (showLoading) {
            state = TvScreenView.SEARCHING;
            screen.invalidate();
        }
        serverClient.loadEvents(serverBase, new ServerClient.EventsCallback() {
            @Override public void onSuccess(List<Event> loaded) {
                main.post(() -> {
                    // Una respuesta vieja no puede devolvernos al menú si el
                    // usuario ya empezó a reproducir un evento.
                    if (!showLoading && state != TvScreenView.EVENTS) return;
                    events.clear();
                    events.addAll(loaded);
                    if (showLoading) state = TvScreenView.EVENTS;
                    selectedEvent = NavigationState.clamp(selectedEvent, events.size());
                    eventOffset = NavigationState.offsetFor(selectedEvent, events.size(), 8, 5);
                    screen.invalidate();
                    for (Event event : loaded) loadLogo(event);
                });
            }

            @Override public void onError(Exception error) {
                main.post(() -> {
                    if (!showLoading && (state != TvScreenView.EVENTS || requestedFromState != TvScreenView.EVENTS)) return;
                    state = TvScreenView.ERROR;
                    screen.invalidate();
                    Toast.makeText(MainActivity.this, "No se pudo cargar el servidor", Toast.LENGTH_SHORT).show();
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

    private void preview(Source source) {
        state = TvScreenView.PREVIEW;
        previewAction = 0;
        playerMessage = "Cargando preview...";
        playback.preview(source);
        screen.invalidate();
    }

    private void openPipEventPicker() {
        if (events.size() < 2) {
            Toast.makeText(this, "No hay un segundo evento disponible", Toast.LENGTH_SHORT).show();
            return;
        }
        pipEvent = pipEvent == selectedEvent ? (selectedEvent + 1) % events.size() : pipEvent;
        pipEventOffset = NavigationState.offsetFor(pipEvent, events.size(), 8, 5);
        state = TvScreenView.PIP_EVENTS;
        screen.invalidate();
    }

    private void showPipSources() {
        if (events.get(pipEvent).sources.isEmpty()) return;
        pipSource = 0;
        pipSourceOffset = 0;
        state = TvScreenView.PIP_SOURCES;
        screen.invalidate();
    }

    private void startPip(Source source) {
        playback.startPip(source);
        state = TvScreenView.DUAL;
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
        playback.releaseAll();
        state = TvScreenView.SOURCES;
        screen.invalidate();
    }

    private void back() {
        if (state == TvScreenView.DUAL) {
            playback.closePip();
            state = TvScreenView.PLAYER;
        } else if (state == TvScreenView.PLAYER) {
            state = TvScreenView.PREVIEW;
            playback.showPreview();
        } else if (state == TvScreenView.PREVIEW) {
            state = TvScreenView.SOURCES;
            playback.stopPrimary();
            playback.releaseAll();
        } else if (state == TvScreenView.PIP_SOURCES) {
            state = TvScreenView.PIP_EVENTS;
        } else if (state == TvScreenView.PIP_EVENTS) {
            state = TvScreenView.PREVIEW;
        } else if (state == TvScreenView.SOURCES) {
            state = TvScreenView.EVENTS;
        } else if (state == TvScreenView.EVENTS || state == TvScreenView.ERROR) {
            finish();
            return;
        }
        screen.invalidate();
    }

    private void tap(float y) {
        if (state == TvScreenView.EVENTS && !events.isEmpty()) {
            int item = eventOffset + (int) ((y - 115) / 52);
            if (item >= 0 && item < events.size()) { selectedEvent = item; showSources(); }
        } else if (state == TvScreenView.SOURCES && !events.isEmpty()) {
            int item = sourceOffset + (int) ((y - 145) / 48);
            if (item >= 0 && item < events.get(selectedEvent).sources.size()) { selectedSource = item; preview(events.get(selectedEvent).sources.get(item)); }
        } else if (state == TvScreenView.PIP_EVENTS && !events.isEmpty()) {
            int item = pipEventOffset + (int) ((y - 115) / 52);
            if (item >= 0 && item < events.size()) { pipEvent = item; showPipSources(); }
        } else if (state == TvScreenView.PIP_SOURCES && !events.isEmpty() && !events.get(pipEvent).sources.isEmpty()) {
            int item = pipSourceOffset + (int) ((y - 145) / 48);
            if (item >= 0 && item < events.get(pipEvent).sources.size()) { pipSource = item; startPip(events.get(pipEvent).sources.get(item)); }
        } else if (state == TvScreenView.PREVIEW && playback.isReady()) {
            state = TvScreenView.PLAYER;
            playback.enterFullscreen();
            screen.invalidate();
        }
    }

    @Override public int state() { return state; }
    @Override public List<Event> events() { return events; }
    @Override public int selectedEvent() { return selectedEvent; }
    @Override public int eventOffset() { return eventOffset; }
    @Override public int selectedSource() { return selectedSource; }
    @Override public int sourceOffset() { return sourceOffset; }
    @Override public int pipEvent() { return pipEvent; }
    @Override public int pipEventOffset() { return pipEventOffset; }
    @Override public int pipSource() { return pipSource; }
    @Override public int pipSourceOffset() { return pipSourceOffset; }
    @Override public int previewAction() { return previewAction; }
    @Override public String playerMessage() { return playerMessage; }
    @Override public Bitmap logo(String url) { return logos.get(url); }
    @Override public String playbackLabel() {
        if (events.isEmpty() || selectedEvent >= events.size()) return "";
        Event event = events.get(selectedEvent);
        if (selectedSource >= event.sources.size()) return event.title;
        return event.title + " · " + event.sources.get(selectedSource).name;
    }
    @Override public void onBack() { back(); }
    @Override public void onTouch(float y) { tap(y); }

    @Override public void onDpad(int keyCode) {
        if (state == TvScreenView.ERROR && (keyCode == KeyEvent.KEYCODE_DPAD_CENTER || keyCode == KeyEvent.KEYCODE_ENTER)) { discoverServer(); return; }
        if (keyCode == KeyEvent.KEYCODE_DPAD_UP || keyCode == KeyEvent.KEYCODE_DPAD_DOWN) {
            int direction = keyCode == KeyEvent.KEYCODE_DPAD_UP ? -1 : 1;
            if (state == TvScreenView.EVENTS && !events.isEmpty()) {
                selectedEvent = NavigationState.clamp(selectedEvent + direction, events.size());
                eventOffset = NavigationState.offsetFor(selectedEvent, events.size(), 8, 5);
            }
            if (state == TvScreenView.SOURCES && !events.isEmpty() && !events.get(selectedEvent).sources.isEmpty()) {
                selectedSource = NavigationState.clamp(selectedSource + direction, events.get(selectedEvent).sources.size());
                sourceOffset = NavigationState.offsetFor(selectedSource, events.get(selectedEvent).sources.size(), 8, 4);
            }
            if (state == TvScreenView.PREVIEW && !events.isEmpty() && !events.get(selectedEvent).sources.isEmpty()) {
                selectedSource = NavigationState.clamp(selectedSource + direction, events.get(selectedEvent).sources.size());
                preview(events.get(selectedEvent).sources.get(selectedSource));
            }
            if ((state == TvScreenView.PLAYER || state == TvScreenView.DUAL) && !events.isEmpty() && !events.get(selectedEvent).sources.isEmpty()) {
                selectedSource = NavigationState.clamp(selectedSource + direction, events.get(selectedEvent).sources.size());
                playback.switchPrimary(events.get(selectedEvent).sources.get(selectedSource));
                screen.showPlaybackOverlay();
            }
            if (state == TvScreenView.PIP_EVENTS && !events.isEmpty()) {
                pipEvent = NavigationState.clamp(pipEvent + direction, events.size());
                pipEventOffset = NavigationState.offsetFor(pipEvent, events.size(), 8, 5);
            }
            if (state == TvScreenView.PIP_SOURCES && !events.get(pipEvent).sources.isEmpty()) {
                pipSource = NavigationState.clamp(pipSource + direction, events.get(pipEvent).sources.size());
                pipSourceOffset = NavigationState.offsetFor(pipSource, events.get(pipEvent).sources.size(), 8, 4);
            }
            screen.invalidate(); return;
        }
        if (keyCode == KeyEvent.KEYCODE_DPAD_LEFT || keyCode == KeyEvent.KEYCODE_DPAD_RIGHT) {
            if (state == TvScreenView.PREVIEW) { previewAction = keyCode == KeyEvent.KEYCODE_DPAD_LEFT ? 0 : 1; screen.invalidate(); return; }
            if (state == TvScreenView.DUAL && keyCode == KeyEvent.KEYCODE_DPAD_RIGHT) {
                int event = selectedEvent; selectedEvent = pipEvent; pipEvent = event;
                int source = selectedSource; selectedSource = pipSource; pipSource = source;
                playback.swap(); screen.showPlaybackOverlay(); return;
            }
        }
    }

    @Override public void onConfirm() {
        if (state == TvScreenView.ERROR) { discoverServer(); return; }
        if (state == TvScreenView.EVENTS) showSources();
        else if (state == TvScreenView.SOURCES && !events.get(selectedEvent).sources.isEmpty()) preview(events.get(selectedEvent).sources.get(selectedSource));
        else if (state == TvScreenView.PREVIEW && playback.isReady()) {
            if (previewAction == 1) openPipEventPicker();
            else { state = TvScreenView.PLAYER; playback.enterFullscreen(); }
        } else if (state == TvScreenView.PIP_EVENTS) showPipSources();
        else if (state == TvScreenView.PIP_SOURCES && !events.get(pipEvent).sources.isEmpty()) startPip(events.get(pipEvent).sources.get(pipSource));
        screen.invalidate();
    }

    @Override public void onBackPressed() { back(); }

    @Override protected void onStop() {
        super.onStop();
        resumePlaybackOnStart = state == TvScreenView.PLAYER || state == TvScreenView.DUAL;
        if (resumePlaybackOnStart) {
            playback.pauseAll();
        }
    }

    @Override protected void onStart() {
        super.onStart();
        if (resumePlaybackOnStart && (state == TvScreenView.PLAYER || state == TvScreenView.DUAL)) {
            playback.resumeAll();
        }
        resumePlaybackOnStart = false;
    }

    @Override protected void onDestroy() {
        main.removeCallbacks(discoveryTimeout);
        main.removeCallbacks(refreshTask);
        stopDiscovery();
        playback.release();
        network.shutdownNow();
        serverClient.close();
        super.onDestroy();
    }


}
