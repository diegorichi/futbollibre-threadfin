#!/bin/bash
cd "$(dirname "$0")"

source `pwd`/config.sh

echo "--- Iniciando proceso diario $(date) ---"

$PYTHON_VENV src/futbol.py $1
#python3 src/futbol.py $1

echo "--- Proceso finalizado ---"
