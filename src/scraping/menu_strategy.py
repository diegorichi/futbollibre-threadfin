"""Compatibilidad con la estructura anterior basada en ``#menu``."""


class MenuStrategy:
    nombre = "menu"

    def extraer(self, driver):
        return driver.execute_script(
            """
            return Array.from(document.querySelectorAll('#menu > li')).map(li => ({
                nombre: li.querySelector('div span')
                    ? li.querySelector('div span').textContent.trim() : '',
                hora: li.querySelector('div div time')
                    ? li.querySelector('div div time').textContent.trim() : '00:00',
                logo: li.querySelector('div div img')
                    ? li.querySelector('div div img').src : '',
                opciones: Array.from(li.querySelectorAll('ul a')).map(a => ({
                    url: a.href,
                    canal: a.querySelector('span')
                        ? a.querySelector('span').textContent.trim() : 'Opción'
                }))
            }));
            """
        ) or []
