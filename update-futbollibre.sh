#!/bin/bash
cd "$(dirname "$0")"

PROJECT_ROOT="$(pwd)"
if command -v flock >/dev/null 2>&1; then
    exec 9>"$PROJECT_ROOT/.update-futbollibre.lock"
    if ! flock -n 9; then
        echo "Ya hay otra actualización de Fútbol Libre en curso."
        exit 2
    fi
fi

source `pwd`/config.sh

echo "--- Iniciando proceso diario $(date) ---"

$PYTHON_VENV src/futbol.py $1

echo "--- Proceso finalizado ---"
