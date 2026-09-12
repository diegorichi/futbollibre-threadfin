---
name: futbol-principal-architecture
description: "Desarrollo senior y lectura arquitectónica del sistema Fútbol Libre; usar al cambiar scraping, servidor, streams, APK, HA, NTFY, descubrimiento o PiP."
---

# Fútbol Libre: principal engineer y arquitectura

Usá este skill cuando la tarea afecte más de un límite del sistema o pueda romper el contrato entre scraper, servidor y Android TV.

## Criterio de trabajo

- Leer primero [la arquitectura](../../docs/ARCHITECTURE.md) y confirmar en el código los consumidores reales antes de modificar nombres, formatos, procesos o endpoints.
- Pensar como principal engineer: preservar contratos, reducir acoplamiento, preferir cambios reversibles y separar diagnóstico de comportamiento operativo.
- No declarar que existe una capacidad solo porque está mencionada en documentación. Si no hay implementación comprobable, marcarla como pendiente.
- En migraciones, comparar salida vieja/nueva con la misma configuración y cubrir todos los callers antes de retirar un legado.
- Mantener secretos y configuración local fuera del código y no exponer rutas absolutas internas en respuestas o UI.

## Enrutamiento

- Scraping, extracción de eventos, HLS, M3U/XML/JSON y progreso: leer las secciones de scraping y publicación.
- Flask, procesos, cron, mDNS/UDP y API: leer servidor y descubrimiento.
- APK, instalación, actualización, reproducción, visualización y PiP: leer cliente Android TV.
- NTFY: leer la integración opcional; no confundir notificación de cambios de URLs con notificación de agenda.

## Límites que no se deben inventar

- NTFY no es la salida principal del scraping: el scraper lo usa para avisar cambios reales en URLs inválidas; la agenda usa NTFY mediante `AgendaService`.
- El PiP actual es dual playback dentro de la Activity, con un segundo `PlayerView` muteado. No es evidencia de soporte de Android system PiP (`Picture-in-Picture`).
- La extracción de eventos no prueba que un stream sea reproducible: una fuente solo entra como disponible si se obtiene una URL HLS válida.
