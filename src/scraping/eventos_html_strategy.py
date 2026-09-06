"""Extracción de eventos cuyo canal apunta a ``eventos*.html``."""


class EventosHtmlStrategy:
    nombre = "eventos-html"

    def extraer(self, driver):
        return driver.execute_script(
            """
            const resultado = [];
            const vistos = new Set();

            for (const li of document.querySelectorAll('li')) {
                const eventoAnchor = Array.from(li.children).find(anchor =>
                    anchor.matches('a[href$="#"], a.active') &&
                    anchor.querySelector('span.t, span') &&
                    !anchor.matches('a[href*="eventos.html"], a[href*="eventos12.html"]')
                );
                const anchors = Array.from(
                    li.querySelectorAll(
                        'a[href*="eventos.html"], a[href*="eventos12.html"]'
                    )
                );

                if (!eventoAnchor || !anchors.length) continue;

                const horaNode = eventoAnchor.querySelector('span.t, span');
                const nombre = Array.from(eventoAnchor.childNodes)
                    .filter(node => node !== horaNode)
                    .map(node => node.textContent || '')
                    .join(' ')
                    .replace(/\\s+/g, ' ')
                    .trim();
                const hora = horaNode ? horaNode.textContent.trim() : '00:00';
                const logoNode = li.querySelector('img');

                for (const anchor of anchors) {
                    const calidad = anchor.querySelector('span');
                    const canal = Array.from(anchor.childNodes)
                        .filter(node => node !== calidad)
                        .map(node => node.textContent || '')
                        .join(' ')
                        .replace(/\\s+/g, ' ')
                        .trim();
                    const opcion = {
                        url: anchor.href,
                        canal: canal || 'Opción',
                    };
                    const clave = `${nombre}|${hora}|${opcion.url}`;
                    if (vistos.has(clave)) continue;
                    vistos.add(clave);
                    resultado.push({
                        nombre,
                        hora,
                        logo: logoNode ? logoNode.src : '',
                        opciones: [opcion],
                    });
                }
            }

            const agrupados = new Map();
            for (const evento of resultado) {
                const clave = `${evento.nombre}|${evento.hora}|${evento.logo}`;
                if (!agrupados.has(clave)) {
                    agrupados.set(clave, {
                        nombre: evento.nombre,
                        hora: evento.hora,
                        logo: evento.logo,
                        opciones: [],
                    });
                }
                agrupados.get(clave).opciones.push(...evento.opciones);
            }
            return Array.from(agrupados.values());
            """
        ) or []
