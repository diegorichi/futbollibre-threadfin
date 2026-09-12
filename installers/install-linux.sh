#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
    if ! command -v apt-get >/dev/null 2>&1; then
        echo "Docker no está instalado y este instalador solo automatiza Debian/Ubuntu." >&2
        echo "Instalá Docker Engine manualmente y volvé a ejecutar este archivo." >&2
        exit 1
    fi
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose-plugin
    sudo systemctl enable --now docker
fi

if ! docker info >/dev/null 2>&1; then
    if sudo docker info >/dev/null 2>&1; then
        DOCKER=(sudo docker)
    else
        echo "Docker está instalado pero no está disponible. Iniciá Docker y reintentá." >&2
        exit 1
    fi
else
    DOCKER=(docker)
fi

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "Se creó .env desde .env.example. Revisá la configuración antes de actualizar sitios."
fi

"${DOCKER[@]}" compose up --build -d
echo "Fútbol Libre disponible en http://localhost:8080"
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open http://localhost:8080 >/dev/null 2>&1 || true
fi
