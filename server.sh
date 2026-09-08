#!/bin/bash
cd "$(dirname "$0")"

source `pwd`/config.sh

echo "--- Iniciando server ---"

PYTHONPATH=src $PYTHON_VENV -m server.api_service

echo "--- Proceso finalizado ---"
