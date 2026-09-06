"""Extracción de layouts modernos con ``time`` y canales dentro de ``ul``."""


class StructuredTimeStrategy:
    nombre = "layout-time"

    def extraer(self, driver):
        return driver.execute_script(
            """
            const resultado = [];
            for (const li of document.querySelectorAll('li')) {
                const header = li.querySelector(':scope > div');
                const horaNode = header ? header.querySelector('time') : null;
                const anchors = Array.from(li.querySelectorAll('a[href]')).filter(anchor => {
                    const href = anchor.getAttribute('href') || '';
                    return href && href !== '#' && anchor !== header &&
                        !anchor.matches('a[href="#"], a.active');
                });
                if (!header || !horaNode || !anchors.length) continue;

                const nombres = Array.from(header.querySelectorAll('span'))
                    .map(span => span.textContent.replace(/\\s+/g, ' ').trim())
                    .filter(Boolean);
                const nombre = nombres.sort((a, b) => b.length - a.length)[0] || '';
                resultado.push({
                    nombre,
                    hora: horaNode.textContent.replace(/\\s+/g, ' ').trim(),
                    logo: (header.querySelector('img') || {}).src || '',
                    opciones: anchors.map(anchor => ({
                        url: anchor.href,
                        canal: anchor.textContent.replace(/\\s+/g, ' ').trim() || 'Opción'
                    }))
                });
            }
            return resultado;
            """
        ) or []
