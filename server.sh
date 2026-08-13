#!/bin/bash
cd "$(dirname "$0")"

source `pwd`/config.sh

echo "--- Iniciando server ---"

$PYTHON_VENV server/api_service.py

echo "--- Proceso finalizado ---"
