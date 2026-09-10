#!/usr/bin/env python3
"""Fetch the first page of football sites from SearXNG."""

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = Path(os.getenv("ENV_FILE", PROJECT_ROOT / ".env"))
if not ENV_FILE.is_absolute():
    ENV_FILE = PROJECT_ROOT / ENV_FILE
ENV = {**dotenv_values(ENV_FILE), **os.environ}

SEARCH_URL = ENV.get("SEARXNG_SEARCH_URL", "http://192.168.0.168/search")
ENGINE = ENV.get("SEARXNG_ENGINE", "duckduckgo")
QUERY = ENV.get("SEARXNG_QUERY", "futbol libre")
URLS_FILE = Path(ENV.get("FUTBOL_LIBRE_URL_FILE", PROJECT_ROOT / "futbol_libre_urls.env"))
if not URLS_FILE.is_absolute():
    URLS_FILE = PROJECT_ROOT / URLS_FILE


def fetch_urls() -> list[str]:
    params = urlencode({"q": QUERY, "engines": ENGINE, "format": "json"})

    resp_ommit = urlopen(Request(f"{SEARCH_URL}"), timeout=30)

    request = Request(f"{SEARCH_URL}?{params}", headers={"Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)

    urls = []
    seen = set()
    for result in payload.get("results", [])[:10]:
        url = (result.get("url") or "").strip()
        if url.startswith(("http://", "https://")) and url not in seen:
            urls.append(url)
            seen.add(url)
    if not urls:
        engines = payload.get("unresponsive_engines", [])
        detail = f" Motores sin respuesta: {engines}." if engines else ""
        raise RuntimeError(f"SearXNG no devolvió URLs.{detail}")
    return urls


def write_urls(urls: list[str]) -> None:
    URLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    extra_url = dotenv_values(URLS_FILE).get("FUTBOL_LIBRE_EXTRA_URL", "")
    temporary = URLS_FILE.with_suffix(URLS_FILE.suffix + ".tmp")
    temporary.write_text(
        "# Generado por update-futbol-libre-sites.sh; no editar manualmente.\n"
        f'FUTBOL_LIBRE_URL="{",".join(urls)}"\n'
        f'FUTBOL_LIBRE_EXTRA_URL="{extra_url}"\n',
        encoding="utf-8",
    )
    temporary.replace(URLS_FILE)


def main() -> int:
    try:
        urls = fetch_urls()
        write_urls(urls)
    except Exception as error:
        print(f"No se pudieron actualizar los sitios desde SearXNG: {error}", file=sys.stderr)
        return 1

    print(f"Sitios actualizados desde {ENGINE}: {len(urls)}")
    for index, url in enumerate(urls, start=1):
        print(f"{index}. {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
