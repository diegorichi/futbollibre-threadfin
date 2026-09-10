"""Extracción de agendas que publican eventos como ``time`` y texto."""


class AgendaTimeStrategy:
    nombre = "agenda-time"

    def extraer(self, driver):
        return driver.execute_script(
            """
            const resultado = [];
            const horaValida = /^([01]\\d|2[0-3]):[0-5]\\d$/;

            for (const timeNode of document.querySelectorAll('time')) {
                const hora = timeNode.textContent.replace(/\\s+/g, ' ').trim();
                if (!horaValida.test(hora)) continue;

                // El <li> contiene el encabezado y el submenu con las
                // fuentes. El contenedor de la agenda completa tiene varias
                // etiquetas time y nunca se usa como bloque de evento.
                let bloque = timeNode.closest('li');
                if (!bloque || bloque.querySelectorAll('time').length !== 1) {
                    bloque = timeNode.parentElement;
                    while (bloque && bloque !== document.body &&
                           bloque.querySelectorAll('time').length !== 1) {
                        bloque = bloque.parentElement;
                    }
                }
                if (!bloque) continue;

                const descripcion = bloque.querySelector('.descripcion');
                const nombre = descripcion
                    ? descripcion.textContent.replace(/\\s+/g, ' ').trim()
                    : Array.from(bloque.querySelectorAll('span'))
                        .filter(span => !span.closest('a'))
                        .map(span => span.textContent.replace(/\\s+/g, ' ').trim())
                        .filter(texto => texto && texto !== '▼')
                        .sort((a, b) => b.length - a.length)[0] || '';
                if (!nombre) continue;

                const opciones = Array.from(bloque.querySelectorAll('a[href]'))
                    .map(anchor => ({
                        url: anchor.href,
                        canal: anchor.querySelector('span:not(.play)')?.textContent
                            .replace(/\\s+/g, ' ').trim() ||
                            anchor.textContent.replace(/\\s+/g, ' ').trim() || 'Opción'
                    }))
                    .filter(opcion => /\\/event/i.test(opcion.url));

                const clave = `${nombre}|${hora}|${opciones.map(opcion => opcion.url).join(',')}`;
                if (resultado.some(evento => evento.clave === clave)) continue;
                resultado.push({
                    clave,
                    nombre,
                    hora,
                    logo: (bloque.querySelector('img') || {}).src || '',
                    opciones
                });
            }

            return resultado.map(({clave, ...evento}) => evento);
            """
        ) or []
