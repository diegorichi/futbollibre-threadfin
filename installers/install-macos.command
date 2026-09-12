#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
    if ! command -v brew >/dev/null 2>&1; then
        echo "Falta Docker Desktop. Instalalo desde https://www.docker.com/products/docker-desktop/"
        read -r -p "Presioná Enter cuando esté instalado..."
    else
        brew install --cask docker
    fi
fi

open -a Docker
echo "Esperando a Docker Desktop..."
for _ in {1..60}; do
    if docker info >/dev/null 2>&1; then break; fi
    sleep 2
done
docker info >/dev/null 2>&1 || { echo "Docker Desktop no inició." >&2; exit 1; }

if [[ ! -f .env ]]; then cp .env.example .env; fi
docker compose up --build -d
echo "Fútbol Libre disponible en http://localhost:8080"
open http://localhost:8080
