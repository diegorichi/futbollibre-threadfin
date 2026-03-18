#!/bin/bash
cd "$(dirname "$0")"

source `pwd`/config.sh

echo "--- Iniciando proceso de agenda diario $(date) ---"

$PYTHON_VENV agenda.py

echo "--- Proceso finalizado ---"
