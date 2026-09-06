"""Sigue un link de canal y busca playbackURL o una URL HLS m3u8."""

import re
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException

from .browser_driver import crear_driver


PLAYBACK_URL = re.compile(r"\bplaybackURL\b\s*[:=]\s*[\"'](https?://[^\"']+)[\"']", re.I)
M3U8_URL = re.compile(r"https?://[^\s\"'<>\\]+\.m3u8(?:\?[^\s\"'<>\\]*)?", re.I)


def extraer_url_stream(texto):
    texto = (texto or "").replace("\\/", "/")
    playback = PLAYBACK_URL.search(texto)
    if playback:
        return playback.group(1).replace("\\/", "/"), "playbackURL"
    m3u8 = M3U8_URL.search(texto)
    if m3u8:
        return m3u8.group(0).replace("\\/", "/"), "m3u8"
    return None, None


def seguir_link_y_extraer_stream(driver, url, espera=5):
    try:
        driver.switch_to.default_content()
        driver.get(url)

        try:
            driver.switch_to.frame("embedIframe")
        except Exception:
            pass

        resultado = None

        def recorrer_contexto():
            nonlocal resultado
            if resultado and resultado[0]:
                return

            resultado = extraer_url_stream(driver.page_source)
            if resultado[0]:
                return

            for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
                try:
                    driver.switch_to.frame(iframe)
                    recorrer_contexto()
                    driver.switch_to.parent_frame()
                    if resultado and resultado[0]:
                        return
                except Exception:
                    try:
                        driver.switch_to.default_content()
                    except WebDriverException:
                        pass
                    return

        import time
        time.sleep(espera)
        recorrer_contexto()
        return resultado or (None, None)
    finally:
        try:
            driver.switch_to.default_content()
        except WebDriverException:
            pass


def _seguir_con_driver(url, espera, driver_factory):
    driver = driver_factory()
    try:
        return seguir_link_y_extraer_stream(driver, url, espera)
    finally:
        try:
            driver.quit()
        except WebDriverException:
            pass


class StreamExtractionPool:
    """Planifica seguimientos seriales o concurrentes sin compartir Selenium."""

    def __init__(self, driver, paralelo=False, workers=2, espera=5, driver_factory=None):
        self.driver = driver
        self.paralelo = paralelo
        self.espera = espera
        self.driver_factory = driver_factory or crear_driver
        self.executor = ThreadPoolExecutor(max_workers=workers) if paralelo else None
        self.pending = {}
        self.results = {}
        self.lock = Lock()

    def submit(self, url):
        if not url or url in self.pending:
            return
        if self.paralelo:
            self.pending[url] = self.executor.submit(
                _seguir_con_driver, url, self.espera, self.driver_factory
            )
        else:
            self.pending[url] = None

    def result(self, url):
        with self.lock:
            if url in self.results:
                return self.results[url]
        if self.paralelo:
            resultado = self.pending[url].result()
        else:
            resultado = seguir_link_y_extraer_stream(self.driver, url, self.espera)
        with self.lock:
            self.results[url] = resultado
        return resultado

    def close(self):
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None
