#!/bin/bash
cd "$(dirname "$0")"

source `pwd`/config.sh

echo "--- Iniciando proceso diario $(date) ---"

$PYTHON_VENV futbol.py $1

echo "--- Proceso finalizado ---"
