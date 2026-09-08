"""Configuración única de Chrome para scraping."""

import os

from dotenv import load_dotenv
from selenium import webdriver


load_dotenv(os.getenv("ENV_FILE", ".env"))

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def _env_bool(name, default=True):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def crear_driver():
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-agent={USER_AGENT}")
    options.add_argument("--window-size=1440,900")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    if _env_bool("HEADLESS", default=True):
        options.add_argument("--headless=new")
    return webdriver.Chrome(options=options)
