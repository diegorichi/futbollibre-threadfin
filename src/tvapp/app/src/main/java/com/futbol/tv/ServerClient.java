package com.futbol.tv;

import com.futbol.tv.model.Event;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** HTTP boundary for the futbol-server API. */
public final class ServerClient {
    public interface EventsCallback {
        void onSuccess(List<Event> events);
        void onError(Exception error);
    }

    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    public void loadEvents(String baseUrl, EventsCallback callback) {
        executor.execute(() -> {
            try {
                String body = get(baseUrl.replaceAll("/$", "") + "/api/v1/events");
                JSONArray array = new JSONObject(body).optJSONArray("events");
                List<Event> result = new ArrayList<>();
                if (array != null) {
                    for (int i = 0; i < array.length(); i++) result.add(Event.from(array.getJSONObject(i)));
                }
                callback.onSuccess(result);
            } catch (Exception error) {
                callback.onError(error);
            }
        });
    }

    public void close() { executor.shutdownNow(); }

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
}
