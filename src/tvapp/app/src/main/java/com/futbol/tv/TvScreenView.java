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
        void onBack(); void onDpad(int keyCode); void onConfirm(); void onTouch(float x, float y);
    }

    private final Host host;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final float density;
    private final Handler overlayHandler = new Handler();
    private boolean playbackOverlayVisible;

    public TvScreenView(Context context, Host host) {
        super(context);
        this.host = host;
        density = getResources().getDisplayMetrics().density;
        setFocusable(true);
        requestFocus();
    }

    private float d(float value) { return value * density; }
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

    private void header(Canvas c, String title) { text(c, title, 70, 62, 30, Color.WHITE, true); text(c, "Fútbol TV", 70, 96, 16, Color.rgb(94,234,212), true); }

    private void drawEvents(Canvas c, boolean forPip) {
        List<Event> events = host.events();
        header(c, forPip ? "Elegí el segundo evento para PiP" : "Eventos");
        if (events.isEmpty()) { text(c, "No hay eventos disponibles", 80, 170, 22, Color.LTGRAY, false); return; }
        int offset = forPip ? host.pipEventOffset() : host.eventOffset();
        int selected = forPip ? host.pipEvent() : host.selectedEvent();
        for (int i = offset; i < Math.min(events.size(), offset + 8); i++) {
            Event event = events.get(i); float y = 145 + (i - offset) * 52;
            if (i == selected) { paint.setColor(Color.rgb(25, 57, 77)); c.drawRoundRect(d(55), d(y - 30), getWidth() - d(55), d(y + 14), d(8), d(8), paint); }
            drawLogo(c, event, 80, y - 24, 34);
            text(c, event.startsAt.length() >= 16 ? event.startsAt.substring(11, 16) : "--:--", 125, y, 20, Color.rgb(94,234,212), true);
            text(c, event.title, 215, y, 21, Color.WHITE, i == selected);
            text(c, event.sources.size() + " fuente" + (event.sources.size() == 1 ? "" : "s"), 780, y, 16, Color.LTGRAY, false);
        }
        text(c, forPip ? "El principal sigue reproduciendo · OK para ver sus fuentes" : "OK para seleccionar · Flechas para desplazarte", 70, 610, 16, Color.LTGRAY, false);
    }

    private void drawUpdate(Canvas c) {
        header(c, "Actualización disponible");
        text(c, "Nueva versión " + host.updateVersion(), 80, 180, 25, Color.WHITE, true);
        text(c, host.updateStatus(), 80, 225, 18, Color.LTGRAY, false);
        text(c, "OK para descargar e instalar · Back para continuar", 80, 285, 18, Color.rgb(94,234,212), true);
    }

    private void drawSources(Canvas c) {
        Event event = host.events().get(host.selectedEvent());
        header(c, event.title); text(c, "Elegí una fuente · Flechas para desplazarte", 70, 135, 18, Color.LTGRAY, false);
        if (event.sources.isEmpty()) { text(c, "No hay fuentes disponibles", 85, 205, 22, Color.LTGRAY, false); return; }
        int visibleEnd = Math.min(event.sources.size(), host.sourceOffset() + 8);
        text(c, (host.sourceOffset() + 1) + "–" + visibleEnd + " de " + event.sources.size(), getWidth() / density - 155, 135, 16, Color.LTGRAY, false);
        for (int i = host.sourceOffset(); i < visibleEnd; i++) { float y = 170 + (i - host.sourceOffset()) * 48; if (i == host.selectedSource()) { paint.setColor(Color.rgb(25,57,77)); c.drawRoundRect(d(55),d(y-27),getWidth()-d(55),d(y+13),d(8),d(8),paint); } text(c, event.sources.get(i).name, 85, y, 20, Color.WHITE, i == host.selectedSource()); }
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
        c.drawColor(Color.rgb(7,17,31)); Event event = host.events().get(host.pipEvent()); header(c,event.title); text(c,"Elegí la fuente para PiP · OK para reproducir muteado",70,135,18,Color.LTGRAY,false);
        for(int i=host.pipSourceOffset();i<Math.min(event.sources.size(),host.pipSourceOffset()+8);i++){float y=170+(i-host.pipSourceOffset())*48;if(i==host.pipSource()){paint.setColor(Color.rgb(25,57,77));c.drawRoundRect(d(55),d(y-27),getWidth()-d(55),d(y+13),d(8),d(8),paint);}text(c,event.sources.get(i).name,85,y,20,Color.WHITE,i==host.pipSource());}
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
        if (event.getAction() == MotionEvent.ACTION_UP) {
            host.onTouch(event.getX() / density, event.getY() / density);
        }
        return true;
    }
}
