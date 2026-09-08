#!/bin/bash
cd "$(dirname "$0")"

source `pwd`/config.sh

echo "--- Iniciando proceso de agenda diario $(date) ---"

PYTHONPATH=src $PYTHON_VENV src/agenda.py

echo "--- Proceso finalizado ---"
