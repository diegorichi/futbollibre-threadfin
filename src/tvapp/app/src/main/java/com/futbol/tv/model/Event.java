package com.futbol.tv.model;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

public final class Event {
    public final String title;
    public final String startsAt;
    public final String logo;
    public final List<Source> sources = new ArrayList<>();

    public Event(String title, String startsAt, String logo) {
        this.title = title;
        this.startsAt = startsAt;
        this.logo = logo;
    }

    public static Event from(JSONObject json) throws Exception {
        Event event = new Event(
                json.optString("title", "Evento"),
                json.optString("starts_at", ""),
                json.optString("logo", ""));
        JSONArray sources = json.optJSONArray("sources");
        if (sources != null) {
            for (int i = 0; i < sources.length(); i++) {
                event.sources.add(Source.from(sources.getJSONObject(i)));
            }
        }
        return event;
    }
}
