---
name: scraping-stream-reliability
description: "Scraping resistente y validación de streams HLS para Fútbol Libre con Selenium."
---

# Scraping y confiabilidad de streams

Usá este skill para modificar scraping, estrategias de eventos, iframes, Selenium, extracción `m3u8`, concurrencia, dominios, CAPTCHA o procesos Chrome.

- Leer `docs/ARCHITECTURE.md` y seguir el flujo real: dominios → eventos → agrupación → opciones → HLS → XML/M3U/JSON.
- Separar detección de evento, extracción de URL y reproducibilidad. Un evento detectado o una opción encontrada no es un stream válido.
- Preservar URLs completas, incluyendo query strings, headers/User-Agent y la fuente de origen cuando sean parte del contrato.
- Al agregar una estrategia, mantener aislamiento por sitio/contexto, recorrer iframes cuando corresponda y evitar duplicar eventos o fuentes.
- En extracción paralela, no compartir Selenium drivers entre workers. Mantener un driver por worker y cerrar Chrome/ChromeDriver aun ante errores.
- Tratar dominio caído, página no disponible, CAPTCHA, iframe inaccesible, URL sin HLS y stream inválido como estados distintos y observables.
- Mantener progreso exacto para sitios y URLs únicas, y escritura atómica de archivos generados.
- Validar con fixtures/tests deterministas antes de probar sitios reales. Las pruebas reales pueden estar bloqueadas por CAPTCHA o cambios externos: reportar esa limitación.
- No borrar estrategias legacy ni cambiar el formato de salida sin rastrear callers, scripts, API, web y Android TV.
- Para notificaciones, enviar NTFY solo ante cambios efectivos; no usar NTFY como sustituto de logs ni como señal de que un stream es reproducible.
