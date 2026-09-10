"""Extrae opciones ``/event...`` asociadas al bloque de una hora."""


class EventLinkTimeStrategy:
    nombre = "event-link-time"

    def extraer(self, driver):
        return driver.execute_script(
            """
            const resultado = [];
            const vistos = new Set();
            const esOpcion = anchor => /(^|\\/)event/i.test(anchor.getAttribute('href') || '');
            const extraerHora = node => {
                if (!node) return '';
                const texto = node.textContent.replace(/\\s+/g, ' ').trim();
                const match = texto.match(/(^|\\s)((?:[01]\\d|2[0-3]):[0-5]\\d)(?=\\s|$)/);
                return match ? match[2] : '';
            };

            for (const anchor of document.querySelectorAll('a[href]')) {
                if (!esOpcion(anchor)) continue;

                let bloque = anchor.closest('li');
                while (bloque && bloque !== document.body) {
                    const horas = bloque.querySelectorAll('time');
                    const opciones = Array.from(bloque.querySelectorAll('a[href]')).filter(esOpcion);
                    const encabezado = Array.from(bloque.children).find(item =>
                        item.matches('a') && !esOpcion(item) && extraerHora(item)
                    );
                    if ((horas.length === 1 || encabezado || extraerHora(bloque)) && opciones.length) break;
                    bloque = bloque.parentElement;
                }
                if (!bloque) continue;

                const encabezado = Array.from(bloque.children).find(item =>
                    item.matches('a') && !esOpcion(item)
                );
                const hora = extraerHora(bloque);
                if (!/^([01]\\d|2[0-3]):[0-5]\\d$/.test(hora)) continue;

                const descripcion = bloque.querySelector('.descripcion');
                let nombre = descripcion
                    ? descripcion.textContent
                    : encabezado
                        ? (() => {
                            const clone = encabezado.cloneNode(true);
                            return clone.textContent.replace(/(^|\\s)((?:[01]\\d|2[0-3]):[0-5]\\d)(?=\\s|$)/, ' ');
                        })()
                        : (() => {
                            const clone = bloque.cloneNode(true);
                            clone.querySelectorAll('a, time').forEach(node => node.remove());
                            return clone.textContent.replace(/(^|\\s)((?:[01]\\d|2[0-3]):[0-5]\\d)(?=\\s|$)/g, ' ');
                        })();
                nombre = nombre.replace(/\\s+/g, ' ').trim();
                if (!nombre) continue;

                const clave = `${nombre}|${hora}`;
                if (vistos.has(clave)) continue;
                vistos.add(clave);
                resultado.push({
                    nombre,
                    hora,
                    logo: (bloque.querySelector('img') || {}).src || '',
                    opciones: Array.from(bloque.querySelectorAll('a[href]'))
                        .filter(esOpcion)
                        .map(item => ({
                            url: item.href,
                            canal: item.textContent.replace(/\\s+/g, ' ').trim() || 'Opción'
                        }))
                });
            }
            return resultado;
            """
        ) or []
