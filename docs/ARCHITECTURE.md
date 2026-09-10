# Arquitectura de Fútbol Libre

Este documento describe lo que está implementado en este checkout. No es una especificación de capacidades futuras.

## Mapa del sistema

```text
cron / Flask / ejecución manual
          |
          v
update-futbollibre.sh -> src/futbol.py
          |
          +-> Selenium: valida dominios
          +-> src/scraping: eventos por estrategias + iframes
          +-> agrupa eventos entre sitios
          +-> extrae playbackURL/.m3u8 por fuente
          +-> publica eventos.xml, eventos.m3u y eventos.json
                                      |
                                      v
                         Flask: web + /api/v1/events
                                      |
                 +--------------------+--------------------+
                 v                                         v
       Android TV: catálogo y HLS                 web / Threadfin / FFmpeg
                 |
       mDNS _futbol._tcp o UDP 45678

agenda.sh / API / agenda.py -> AgendaService -> NTFY y Home Assistant
update-futbol-libre-sites.sh -> SearXNG -> futbol_libre_urls.env
```

## Componentes y contratos

### 1. Scraping y extracción

- Entrada: `FUTBOL_LIBRE_URL_FILE` primero; `.env` queda como fallback.
- `src/futbol.py` crea el driver Selenium, valida cada dominio y conserva los válidos.
- `src/scraping/site_scraper.py` recorre sitios y agrega `fuente` a eventos/opciones.
- `src/scraping/event_extractor.py` combina estrategias HTML, PHP, canal directo, tiempo estructurado, agenda y menú; también recorre iframes.
- `event_matching.py` agrupa eventos equivalentes entre sitios.
- Se separan eventos activos y próximos. La extracción de streams opera sobre las opciones de eventos activos y luego también arma el contrato de eventos de TV.
- `stream_extractor.py` busca `playbackURL` y `.m3u8`, conserva la query string y puede seguir iframes. En modo paralelo cada worker usa su propio Chrome.
- Una detección de evento no implica stream válido. La fuente se publica como disponible solo con URL HLS resultante.

Salidas actuales:

- `eventos.xml`: XMLTV usado por web y servicios de agenda.
- `eventos.m3u`: lista legacy de slots, hasta 100 canales `E01`–`E100`.
- `eventos.json`: salida auxiliar; la API de TV lee XML/M3U mediante `ChannelService` para evitar desalineación.
- `.update-futbollibre.progress.json`: progreso atómico de sitios y streams.

### 2. SearXNG y URLs de sitios

`update-futbol-libre-sites.sh` ejecuta `src/search_sites.py`. El resultado se escribe en `futbol_libre_urls.env` mediante archivo temporal y replace. Si la búsqueda queda vacía o bloqueada, se conserva la lista anterior.

La rutina de validación en `src/futbol.py` elimina dominios inválidos solo si queda al menos uno válido. NTFY se envía únicamente cuando hubo cambios efectivos; no se envía por una ejecución sin cambios.

Esto es mantenimiento de fuentes, no extracción de eventos. La agenda principal corre después por `update-futbollibre.sh` según el cron instalado.

### 3. Servidor Flask y ejecución

- Inicio: `server.sh` ejecuta `PYTHONPATH=src python -m server.api_service` en el puerto `8080`.
- `ProcessRunner` persiste PID y log, recupera estado tras reinicio y detiene el grupo o árbol del proceso para no dejar Chrome/ChromeDriver vivos.
- `update-futbollibre.sh` usa `flock` para impedir ejecuciones concurrentes.
- `/update-url`, `/status` y `/stop-update` controlan la ejecución y el progreso.
- `/api/v1/health` comprueba el servicio.
- `/api/v1/events` entrega `{api_version, generated_at, refresh_after, events}`.
- `/api/v1/discovery` entrega metadatos del servidor.
- `/grilla` y `/canales` sirven la visualización web desde XML/M3U.

### 4. Descubrimiento del servidor por Android TV

El servidor publica `_futbol._tcp.local.` por Zeroconf/mDNS en el puerto 8080. Como fallback escucha broadcast UDP en `45678` y responde a `FUTBOL_DISCOVER_V1`.

La app intenta, en orden práctico: URL explícita `server_url`, mDNS; después de seis segundos, emulador `10.0.2.2:8080` o broadcast UDP. Una vez conectada, consulta `/api/v1/events` y refresca el catálogo cada 60 segundos solo cuando está en la pantalla de eventos, no durante reproducción.

### 5. Android TV, streams y visualización

El flujo de UI es:

```text
buscar servidor -> eventos -> fuentes -> preview -> pantalla completa
                                             |
                                             +-> elegir segundo evento -> fuente -> dual playback
```

`ServerClient` consume `/api/v1/events`. `PlaybackController` usa Media3/ExoPlayer con HLS y el `User-Agent` de cada fuente. La pantalla permite cambiar de fuente y muestra errores sin volver a cargar el catálogo.

El modo llamado PiP en el código crea dos reproductores: el principal ocupa la pantalla y el secundario usa un `PlayerView` más pequeño, muteado, en la esquina inferior. `swap()` intercambia los reproductores. Esto es composición interna de la Activity; no hay `android:supportsPictureInPicture`, `enterPictureInPictureMode()` ni servicio separado que pruebe PiP del sistema Android.

### 6. Actualización del APK

1. Incrementar `versionCode`, `versionName` y `BuildConfig.APP_VERSION_CODE` en `src/tvapp/app/build.gradle`.
2. Compilar con `cd src/tvapp && ./gradlew assembleDebug`.
3. Copiar `app/build/outputs/apk/debug/app-debug.apk` a `output/futbol-tv-debug.apk`.
4. Reiniciar/verificar el servidor con `TV_APP_VERSION_CODE`, `TV_APP_VERSION_NAME` y `TV_APP_APK_PATH` coherentes con el APK publicado.

La app consulta `/api/v1/app` una sola vez después de cargar eventos. Si el `version_code` del servidor es mayor, descarga `/downloads/futbol-tv.apk` y abre el instalador Android mediante `FileProvider`; el usuario debe confirmar la instalación. El endpoint `/tvapp` permite descargar el APK desde navegador.

Instalación manual:

```bash
adb connect IP_DEL_TV:5555
adb install -r output/futbol-tv-debug.apk
```

### 7. NTFY y Home Assistant

Son integraciones separadas:

- `AgendaService.events()` lee `eventos.xml`, filtra por `KEYS`, parsea títulos y deduplica por hora/equipos.
- `update_ntfy()` publica la agenda en `NTFY_URL` con título `Grilla Deportiva`.
- `update_home_assistant()` publica estado y atributos en `HA_URL` usando `HA_TOKEN`; opcionalmente escribe `JSON_FILE`.
- Flask expone `/system-update/ha`, `/system-update/ntfy` y `/system-update/sites` para dispararlas manualmente.

Home Assistant no interviene en el descubrimiento mDNS/UDP ni en el deploy del APK. Si se requiere ese flujo, primero hay que definir e implementar un contrato nuevo.

## Reglas para cambios

- Cambiar primero el contrato en un único punto y luego sus consumidores; barrer referencias residuales con `rg`.
- No eliminar `eventos.xml`, `eventos.m3u`, `eventos.json`, endpoints o nombres de entorno sin identificar consumidores directos e indirectos.
- Mantener la escritura de archivos generados atómica cuando el proceso pueda ser leído por Flask o por otro job.
- Probar, como mínimo, importación/sintaxis, tests focalizados y el endpoint o build afectado. Separar validación local de validación en un TV, host Linux, Home Assistant o sitio real.
- Tratar CAPTCHA, dominios caídos y streams detectados sin HLS como estados explícitos, no como éxitos parciales.

## No confirmado en este repositorio

- No hay un flujo implementado de Home Assistant hacia descubrimiento del server.
- No hay PiP del sistema Android confirmado; solo dual playback dentro de la Activity.
- No se debe asumir que todos los sitios producen streams reproducibles: la cobertura real de sitios requiere validación contra los sitios actuales.
