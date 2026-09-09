# Fútbol TV

Cliente Android TV/Android para el server local de fútbol.

## Flujo

La app descubre el servicio mDNS `_futbol._tcp`, consulta `/api/v1/events` y navega por:

`eventos -> fuentes -> preview -> pantalla completa`

Para probar el emulador sin mDNS se puede iniciar con un `server_url` explícito:

```bash
adb shell am start -n com.futbol.tv/.MainActivity \\
  --es server_url http://10.0.2.2:8080
```
