---
name: android-tv-release
description: "Construcción, instalación, actualización y verificación del cliente Android TV de Fútbol Libre."
---

# Android TV release

Usá este skill para cualquier cambio en `src/tvapp`, el APK, Media3, descubrimiento del servidor, actualización remota o pruebas con `adb`.

- Leer `docs/ARCHITECTURE.md`, `src/tvapp/README.md` y el código consumidor antes de cambiar contratos.
- Mantener sincronizados `versionCode`, `versionName`, `BuildConfig.APP_VERSION_CODE`, `TV_APP_VERSION_CODE` y `TV_APP_VERSION_NAME`.
- Compilar con `cd src/tvapp && ./gradlew assembleDebug` y publicar explícitamente el artefacto en `output/futbol-tv-debug.apk` solo cuando corresponda.
- Verificar el contrato `/api/v1/app` y `/downloads/futbol-tv.apk`; una descarga exitosa no prueba que Android haya instalado el APK.
- Para pruebas, distinguir emulador (`10.0.2.2:8080`), TV físico (`adb connect`) y servidor real. No mezclar sus URLs ni declarar validación de TV físico sin haberla ejecutado.
- Mantener el descubrimiento en mDNS/UDP y la URL explícita como fallback compatible.
- Si se toca PiP, comprobar si se modifica el dual playback actual o si realmente se implementa Android system PiP; no llamar a ambos igual.
- Validar navegación, refresco de catálogo, selección de fuente, preview, reproducción, cambio de fuente, actualización y cierre de PiP cuando el cambio las afecte.
- No subir secretos, APKs temporales de Gradle ni modificar archivos generados fuera del artefacto distribuible.
