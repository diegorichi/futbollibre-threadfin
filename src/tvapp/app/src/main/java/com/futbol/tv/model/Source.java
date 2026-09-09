package com.futbol.tv.model;

import org.json.JSONObject;

public final class Source {
    public final String name;
    public final String url;
    public final String userAgent;

    public Source(String name, String url, String userAgent) {
        this.name = name;
        this.url = url;
        this.userAgent = userAgent;
    }

    public static Source from(JSONObject json) {
        return new Source(
                json.optString("name", "Fuente"),
                json.optString("url", ""),
                json.optString("user_agent", null));
    }
}
