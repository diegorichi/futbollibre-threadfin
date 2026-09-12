package com.futbol.tv;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.os.Handler;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;

import com.futbol.tv.model.Event;

import java.util.List;

/** Dumb TV canvas: drawing and input forwarding only. */
public final class TvScreenView extends View {
    public static final int SEARCHING = 0, EVENTS = 1, SOURCES = 2, PREVIEW = 3,
            PLAYER = 4, ERROR = 5, PIP_EVENTS = 6, PIP_SOURCES = 7, DUAL = 8, UPDATE = 9;

    public interface Host {
        int state();
        List<Event> events();
        int selectedEvent(); int eventOffset(); int selectedSource(); int sourceOffset();
        int pipEvent(); int pipEventOffset(); int pipSource(); int pipSourceOffset();
        int previewAction(); String playerMessage(); Bitmap logo(String url); String playbackLabel();
        String updateVersion(); String updateStatus();
        void onBack(); void onDpad(int keyCode); void onConfirm(); void onTouch(float x, float y); void onSwipe(boolean down);
    }

    private final Host host;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final float density;
    private final Handler overlayHandler = new Handler();
    private boolean playbackOverlayVisible;
    private float downX;
    private float downY;

    public TvScreenView(Context context, Host host) {
        super(context);
        this.host = host;
        density = getResources().getDisplayMetrics().density;
        setFocusable(true);
        requestFocus();
    }

    private float d(float value) { return value * density; }
    private float widthDp() { return getWidth() / density; }
    private float heightDp() { return getHeight() / density; }
    private boolean compactLayout() {
        return getResources().getConfiguration().smallestScreenWidthDp < 600;
    }
    public boolean isCompactLayout() { return compactLayout(); }
    private float compactEventRow() {
        if (heightDp() >= widthDp()) return 88f;
        return Math.max(56f, Math.min(76f, (heightDp() - 130f) / 3f));
    }
    private float compactEventListTop() { return heightDp() >= widthDp() ? 125f : 96f; }
    public float compactEventRowDp() { return compactEventRow(); }
    public float compactEventListTopDp() { return compactEventListTop(); }
    public int visibleRows() {
        if (!compactLayout()) return 8;
        return Math.max(1, Math.min(8, (int) ((heightDp() - compactEventListTop() - 35f) / compactEventRow())));
    }
    private String fit(String value, float maxWidthDp, float sizeDp) {
        if (value == null) return "";
        paint.setTextSize(d(sizeDp));
        if (paint.measureText(value) <= d(maxWidthDp)) return value;
        String suffix = "…";
        while (value.length() > 1 && paint.measureText(value + suffix) > d(maxWidthDp)) {
            value = value.substring(0, value.length() - 1);
        }
        return value + suffix;
    }
    private void text(Canvas c, String value, float x, float y, float size, int color, boolean bold) {
        paint.setColor(color); paint.setTextSize(d(size));
        paint.setTypeface(bold ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
        c.drawText(value, d(x), d(y), paint);
    }

    @Override protected void onDraw(Canvas c) {
        int state = host.state();
        if (state == PREVIEW || state == PLAYER || state == DUAL) {
            if (state == PREVIEW) drawPreview(c);
            if (state == PLAYER || state == DUAL) drawPlaybackOverlay(c);
            return;
        }
        c.drawColor(Color.rgb(7, 17, 31));
        if (state == SEARCHING) { text(c, "Buscando servidor...", 80, 90, 28, Color.WHITE, true); return; }
        if (state == ERROR) { text(c, "No se encontró el servidor", 80, 90, 28, Color.WHITE, true); text(c, "Back para salir · OK para reintentar", 80, 135, 18, Color.LTGRAY, false); return; }
        if (state == UPDATE) { drawUpdate(c); return; }
        if (state == EVENTS) drawEvents(c, false);
        if (state == SOURCES) drawSources(c);
        if (state == PIP_EVENTS) drawEvents(c, true);
        if (state == PIP_SOURCES) drawPipSources(c);
    }

    private void header(Canvas c, String title) {
        float x = compactLayout() ? 24 : 70;
        text(c, fit(title, widthDp() - x * 2, compactLayout() ? 24 : 30), x, compactLayout() ? 42 : 62, compactLayout() ? 24 : 30, Color.WHITE, true);
        text(c, "Fútbol TV", x, compactLayout() ? 68 : 96, compactLayout() ? 14 : 16, Color.rgb(94,234,212), true);
    }

    private void drawEvents(Canvas c, boolean forPip) {
        List<Event> events = host.events();
        header(c, forPip ? "Elegí el segundo evento para PiP" : "Eventos");
        if (events.isEmpty()) { text(c, "No hay eventos disponibles", compactLayout() ? 24 : 80, compactLayout() ? 130 : 170, 22, Color.LTGRAY, false); return; }
        if (compactLayout()) { drawCompactEvents(c, events, forPip); return; }
        int offset = forPip ? host.pipEventOffset() : host.eventOffset();
        int selected = forPip ? host.pipEvent() : host.selectedEvent();
        int rows = visibleRows();
        float left = compactLayout() ? 16 : 55;
        float right = compactLayout() ? widthDp() - 16 : widthDp() - 55;
        for (int i = offset; i < Math.min(events.size(), offset + rows); i++) {
            Event event = events.get(i); float y = compactLayout() ? 120 + (i - offset) * 52 : 145 + (i - offset) * 52;
            if (i == selected) { paint.setColor(Color.rgb(25, 57, 77)); c.drawRoundRect(d(left), d(y - 30), d(right), d(y + 14), d(8), d(8), paint); }
            float logoX = compactLayout() ? 24 : 80;
            drawLogo(c, event, logoX, y - 24, compactLayout() ? 38 : 34);
            float timeX = compactLayout() ? 72 : 125;
            text(c, event.startsAt.length() >= 16 ? event.startsAt.substring(11, 16) : "--:--", timeX, y, compactLayout() ? 17 : 20, Color.rgb(94,234,212), true);
            float titleX = compactLayout() ? 130 : 215;
            String sources = event.sources.size() + " fuente" + (event.sources.size() == 1 ? "" : "s");
            paint.setTextSize(d(compactLayout() ? 13 : 16));
            float sourceWidth = paint.measureText(sources) / density;
            text(c, fit(event.title, right - titleX - sourceWidth - 12, compactLayout() ? 16 : 21), titleX, y, compactLayout() ? 16 : 21, Color.WHITE, i == selected);
            text(c, sources, right - sourceWidth, y, compactLayout() ? 13 : 16, Color.LTGRAY, false);
        }
        text(c, forPip ? (compactLayout() ? "Tocá un evento para elegir su fuente" : "El principal sigue reproduciendo · OK para ver sus fuentes") : (compactLayout() ? "Tocá un evento · Deslizá para desplazarte" : "OK para seleccionar · Flechas para desplazarte"), compactLayout() ? 24 : 70, heightDp() - 24, compactLayout() ? 13 : 16, Color.LTGRAY, false);
    }

    private void drawCompactEvents(Canvas c, List<Event> events, boolean forPip) {
        int offset = forPip ? host.pipEventOffset() : host.eventOffset();
        int selected = forPip ? host.pipEvent() : host.selectedEvent();
        float left = 16, right = widthDp() - 16, titleX = 24, matchX = 92;
        int rows = visibleRows();
        for (int i = offset; i < Math.min(events.size(), offset + rows); i++) {
            Event event = events.get(i);
            float y = compactEventListTop() + (i - offset) * compactEventRow();
            if (i == selected) {
                paint.setColor(Color.rgb(25, 57, 77));
                float padding = compactEventRow() > 80 ? 39 : 29;
                c.drawRoundRect(d(left), d(y - padding), d(right), d(y + padding), d(8), d(8), paint);
            }
            String[] parts = titleParts(event.title);
            String time = event.startsAt.length() >= 16 ? event.startsAt.substring(11, 16) : "--:--";
            text(c, time, titleX, y, 20, Color.rgb(94, 234, 212), true);
            String sources = event.sources.size() + " fuente" + (event.sources.size() == 1 ? "" : "s");
            paint.setTextSize(d(13));
            float sourceWidth = paint.measureText(sources) / density;
            float maxMatch = right - matchX - sourceWidth - 10;
            paint.setTextSize(d(18));
            boolean vertical = paint.measureText(parts[1]) > d(maxMatch) && parts[1].matches("(?s).*\\s+(?i:vs\\.?)\\s+.*");
            if (vertical) {
                String[] teams = parts[1].split("\\s+(?i:vs\\.?)\\s+", 2);
                text(c, fit(teams[0], maxMatch, 16), matchX, y - 12, 16, Color.WHITE, i == selected);
                text(c, "VS", matchX, y + 8, 13, Color.rgb(94, 234, 212), true);
                text(c, fit(teams.length > 1 ? teams[1] : "", maxMatch, 16), matchX, y + 28, 16, Color.WHITE, i == selected);
            } else {
                text(c, fit(parts[1], maxMatch, 18), matchX, y, 18, Color.WHITE, i == selected);
            }
            text(c, fit(parts[0], right - matchX, 12), matchX, y + (compactEventRow() > 80 ? 47 : 30), 12, Color.LTGRAY, false);
            text(c, sources, right - sourceWidth, y, 13, Color.LTGRAY, false);
        }
        text(c, forPip ? "Tocá un evento para elegir su fuente" : "Tocá un evento · Deslizá para desplazarte", 24, heightDp() - 24, 13, Color.LTGRAY, false);
    }

    private String[] titleParts(String title) {
        int separator = title == null ? -1 : title.indexOf(':');
        if (separator > 0 && separator < title.length() - 1) {
            return new String[] { title.substring(0, separator).trim(), title.substring(separator + 1).trim() };
        }
        return new String[] { "", title == null ? "Evento" : title.trim() };
    }

    private void drawUpdate(Canvas c) {
        header(c, "Actualización disponible");
        text(c, "Nueva versión " + host.updateVersion(), 80, 180, 25, Color.WHITE, true);
        text(c, host.updateStatus(), 80, 225, 18, Color.LTGRAY, false);
        text(c, "OK para descargar e instalar · Back para continuar", 80, 285, 18, Color.rgb(94,234,212), true);
    }

    private void drawSources(Canvas c) {
        Event event = host.events().get(host.selectedEvent());
        if (compactLayout()) { drawCompactSources(c, event); return; }
        header(c, event.title); text(c, compactLayout() ? "Elegí una fuente · Deslizá para desplazarte" : "Elegí una fuente · Flechas para desplazarte", compactLayout() ? 24 : 70, compactLayout() ? 100 : 135, compactLayout() ? 14 : 18, Color.LTGRAY, false);
        if (event.sources.isEmpty()) { text(c, "No hay fuentes disponibles", 85, 205, 22, Color.LTGRAY, false); return; }
        int visibleEnd = Math.min(event.sources.size(), host.sourceOffset() + visibleRows());
        float right = widthDp() - (compactLayout() ? 16 : 55);
        text(c, (host.sourceOffset() + 1) + "–" + visibleEnd + " de " + event.sources.size(), right - (compactLayout() ? 95 : 155), compactLayout() ? 100 : 135, compactLayout() ? 13 : 16, Color.LTGRAY, false);
        for (int i = host.sourceOffset(); i < visibleEnd; i++) { float y = (compactLayout() ? 135 : 170) + (i - host.sourceOffset()) * 48; if (i == host.selectedSource()) { paint.setColor(Color.rgb(25,57,77)); c.drawRoundRect(d(compactLayout() ? 16 : 55),d(y-27),d(right),d(y+13),d(8),d(8),paint); } text(c, fit(event.sources.get(i).name, right - (compactLayout() ? 32 : 85), compactLayout() ? 17 : 20), compactLayout() ? 32 : 85, y, compactLayout() ? 17 : 20, Color.WHITE, i == host.selectedSource()); }
    }

    private void drawCompactSources(Canvas c, Event event) {
        header(c, event.title);
        text(c, "Elegí una fuente · Tocá para reproducir", 24, 100, 14, Color.LTGRAY, false);
        int visibleEnd = Math.min(event.sources.size(), host.sourceOffset() + visibleRows());
        float right = widthDp() - 16;
        text(c, (host.sourceOffset() + 1) + "–" + visibleEnd + " de " + event.sources.size(), right - 95, 124, 13, Color.LTGRAY, false);
        for (int i = host.sourceOffset(); i < visibleEnd; i++) {
            float y = 160 + (i - host.sourceOffset()) * 48;
            if (i == host.selectedSource()) {
                paint.setColor(Color.rgb(25, 57, 77));
                c.drawRoundRect(d(16), d(y - 27), d(right), d(y + 13), d(8), d(8), paint);
            }
            text(c, fit(event.sources.get(i).name, right - 32, 17), 32, y, 17, Color.WHITE, i == host.selectedSource());
        }
        text(c, "Deslizá para desplazarte", 24, heightDp() - 24, 13, Color.LTGRAY, false);
    }

    private void drawPreview(Canvas c) {
        paint.setColor(Color.argb(220, 7, 17, 31)); c.drawRect(0, getHeight() - d(125), getWidth(), getHeight(), paint);
        String position = ""; List<Event> events = host.events();
        if (!events.isEmpty() && host.selectedEvent() < events.size()) {
            Event event = events.get(host.selectedEvent());
            if (host.selectedSource() < event.sources.size()) position = event.title + " · " + (host.selectedSource() + 1) + "/" + event.sources.size() + " · " + event.sources.get(host.selectedSource()).name;
        }
        text(c, position, 60, getHeight() / density - 112, 15, Color.rgb(94,234,212), true);
        text(c, host.playerMessage(), 60, getHeight() / density - 88, 18, Color.WHITE, true);
        text(c, host.previewAction() == 0 ? "[Ver en pantalla completa]" : "[Agregar segundo evento en PiP]", 60, getHeight() / density - 53, 18, Color.rgb(94,234,212), true);
        text(c, "◀ ▶ elegir acción · ▲ ▼ cambiar fuente · OK confirmar · Back: fuentes", 60, getHeight() / density - 18, 14, Color.LTGRAY, false);
    }

    public void showPlaybackOverlay() {
        playbackOverlayVisible = true;
        overlayHandler.removeCallbacksAndMessages(null);
        overlayHandler.postDelayed(() -> { playbackOverlayVisible = false; invalidate(); }, 4000);
        invalidate();
    }

    private void drawPlaybackOverlay(Canvas c) {
        if (!playbackOverlayVisible) return;
        float bottom = getHeight() / density - 22;
        String help = host.state() == DUAL
                ? "▲ ▼ cambiar fuente principal · ◀ ▶ intercambiar · Back: cerrar PiP"
                : "▲ ▼ cambiar fuente · Back: volver";
        paint.setColor(Color.argb(205, 7, 17, 31));
        c.drawRect(0, getHeight() - d(58), getWidth(), getHeight(), paint);
        text(c, help, 35, bottom, 14, Color.LTGRAY, false);
        String label = host.playbackLabel();
        paint.setTextSize(d(15)); paint.setTypeface(Typeface.DEFAULT_BOLD);
        float labelWidth = paint.measureText(label);
        text(c, label, getWidth() / density - labelWidth / density - 35, bottom, 15, Color.rgb(94,234,212), true);
    }

    private void drawPipSources(Canvas c) {
        c.drawColor(Color.rgb(7,17,31)); Event event = host.events().get(host.pipEvent()); header(c,event.title); text(c,compactLayout() ? "Elegí la fuente para PiP · Tocá para reproducir" : "Elegí la fuente para PiP · OK para reproducir muteado",compactLayout() ? 24 : 70,compactLayout() ? 100 : 135,compactLayout() ? 14 : 18,Color.LTGRAY,false);
        float right = widthDp() - (compactLayout() ? 16 : 55);
        for(int i=host.pipSourceOffset();i<Math.min(event.sources.size(),host.pipSourceOffset()+visibleRows());i++){float y=(compactLayout() ? 135 : 170)+(i-host.pipSourceOffset())*48;if(i==host.pipSource()){paint.setColor(Color.rgb(25,57,77));c.drawRoundRect(d(compactLayout() ? 16 : 55),d(y-27),d(right),d(y+13),d(8),d(8),paint);}text(c,fit(event.sources.get(i).name,right-(compactLayout() ? 32 : 85),compactLayout() ? 17 : 20),compactLayout() ? 32 : 85,y,compactLayout() ? 17 : 20,Color.WHITE,i==host.pipSource());}
    }

    private void drawLogo(Canvas c, Event event, float x, float y, float size) {
        Bitmap bitmap = host.logo(event.logo);
        if (bitmap != null) c.drawBitmap(bitmap, null, new android.graphics.RectF(d(x),d(y),d(x+size),d(y+size)), paint);
        else { paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(d(2)); paint.setColor(Color.rgb(94,234,212)); c.drawCircle(d(x+size/2),d(y+size/2),d(size/2-2),paint); paint.setStyle(Paint.Style.FILL); }
    }

    @Override public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK) host.onBack();
        else if (keyCode == KeyEvent.KEYCODE_DPAD_CENTER || keyCode == KeyEvent.KEYCODE_ENTER) host.onConfirm();
        else host.onDpad(keyCode);
        return true;
    }

    @Override public boolean onTouchEvent(MotionEvent event) {
        // Durante reproducción esta vista es transparente y no debe tapar los
        // gestos/controles táctiles del PlayerView que está debajo.
        int state = host.state();
        if (state == PLAYER || state == DUAL) return false;
        if (event.getAction() == MotionEvent.ACTION_DOWN) {
            downX = event.getX(); downY = event.getY();
            return true;
        }
        if (event.getAction() == MotionEvent.ACTION_UP) {
            float dx = (event.getX() - downX) / density;
            float dy = (event.getY() - downY) / density;
            if (Math.abs(dy) > 32 && Math.abs(dy) > Math.abs(dx)) {
                // Deslizar hacia arriba muestra los elementos siguientes.
                host.onSwipe(dy < 0);
            } else {
                host.onTouch(event.getX() / density, event.getY() / density);
            }
        }
        return true;
    }
}
