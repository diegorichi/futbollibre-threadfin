package com.futbol.tv;

import android.content.Context;
import android.content.Intent;
import android.net.Uri;

import androidx.core.content.FileProvider;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Checks the server release and delegates installation to Android. */
public final class AppUpdateManager {
    public static final class Release {
        public final int versionCode;
        public final String versionName;
        public final String apkUrl;
        public final String changelog;

        Release(int versionCode, String versionName, String apkUrl, String changelog) {
            this.versionCode = versionCode;
            this.versionName = versionName;
            this.apkUrl = apkUrl;
            this.changelog = changelog;
        }
    }

    public interface CheckCallback {
        void onUpToDate();
        void onUpdateAvailable(Release release);
        void onError(Exception error);
    }

    public interface InstallCallback {
        void onStarted();
        void onError(Exception error);
    }

    private final Context context;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    public AppUpdateManager(Context context) { this.context = context.getApplicationContext(); }

    public void check(String baseUrl, int currentVersionCode, CheckCallback callback) {
        executor.execute(() -> {
            try {
                String body = read(baseUrl.replaceAll("/$", "") + "/api/v1/app");
                JSONObject json = new JSONObject(body);
                Release release = new Release(
                        json.optInt("version_code", 0),
                        json.optString("version_name", ""),
                        absoluteUrl(baseUrl, json.optString("apk_url", "")),
                        json.optString("changelog", ""));
                if (release.versionCode > currentVersionCode) callback.onUpdateAvailable(release);
                else callback.onUpToDate();
            } catch (Exception error) {
                callback.onError(error);
            }
        });
    }

    public void downloadAndInstall(Release release, InstallCallback callback) {
        executor.execute(() -> {
            try {
                File directory = new File(context.getCacheDir(), "updates");
                if (!directory.isDirectory() && !directory.mkdirs()) throw new IllegalStateException("No se pudo crear el directorio de actualización");
                File apk = new File(directory, "futbol-tv.apk");
                download(release.apkUrl, apk);
                Uri uri = FileProvider.getUriForFile(context, context.getPackageName() + ".fileprovider", apk);
                Intent intent = new Intent(Intent.ACTION_VIEW);
                intent.setDataAndType(uri, "application/vnd.android.package-archive");
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_GRANT_READ_URI_PERMISSION);
                context.startActivity(intent);
                callback.onStarted();
            } catch (Exception error) {
                callback.onError(error);
            }
        });
    }

    public void close() { executor.shutdownNow(); }

    private static String absoluteUrl(String baseUrl, String path) {
        if (path.startsWith("http://") || path.startsWith("https://")) return path;
        return baseUrl.replaceAll("/$", "") + "/" + path.replaceFirst("^/", "");
    }

    private static String read(String address) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(address).openConnection();
        connection.setConnectTimeout(5000);
        connection.setReadTimeout(8000);
        try (InputStream input = connection.getInputStream()) {
            byte[] buffer = new byte[4096];
            StringBuilder result = new StringBuilder();
            int count;
            while ((count = input.read(buffer)) != -1) result.append(new String(buffer, 0, count));
            return result.toString();
        } finally { connection.disconnect(); }
    }

    private static void download(String address, File target) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(address).openConnection();
        connection.setConnectTimeout(5000);
        connection.setReadTimeout(15000);
        try (BufferedInputStream input = new BufferedInputStream(connection.getInputStream()); FileOutputStream output = new FileOutputStream(target)) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
        } finally { connection.disconnect(); }
    }
}
