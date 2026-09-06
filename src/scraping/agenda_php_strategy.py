"""Extracción de eventos cuyos canales apuntan a ``eventos.php``."""


class AgendaPhpStrategy:
    nombre = "agenda-eventos-php"

    def extraer(self, driver):
        return driver.execute_script(
            """
            const resultado = [];
            for (const li of document.querySelectorAll('li')) {
                const eventoAnchor = Array.from(li.children).find(anchor =>
                    anchor.matches('a[href$="#"], a.active') &&
                    anchor.querySelector('span.t, span')
                );
                const anchors = Array.from(
                    li.querySelectorAll('a[href*="eventos.php"]')
                );
                if (!eventoAnchor || !anchors.length) continue;

                const horaNode = eventoAnchor.querySelector('span.t, span');
                const nombre = Array.from(eventoAnchor.childNodes)
                    .filter(node => node !== horaNode)
                    .map(node => node.textContent || '')
                    .join(' ')
                    .replace(/\\s+/g, ' ')
                    .trim();
                resultado.push({
                    nombre,
                    hora: horaNode ? horaNode.textContent.trim() : '00:00',
                    logo: (li.querySelector('img') || {}).src || '',
                    opciones: anchors.map(anchor => ({
                        url: anchor.href,
                        canal: (() => {
                            const clone = anchor.cloneNode(true);
                            clone.querySelectorAll('span').forEach(span => span.remove());
                            return clone.textContent.replace(/\\s+/g, ' ').trim() || 'Opción';
                        })()
                    }))
                });
            }
            return resultado;
            """
        ) or []
