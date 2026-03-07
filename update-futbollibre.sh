#!/bin/bash
cd "$(dirname "$0")"

source `pwd`/config.sh

# Definimos el Python del entorno virtual

echo "--- Iniciando proceso diario $(date) ---"

echo "1. Limpiando mapping viejo..."
$PYTHON_VENV threadfin-unmapping.py

echo "2. Extrayendo nuevos canales..."
$PYTHON_VENV futbol.py $1

echo "3. importing agenda in threadfin"
$PYTHON_VENV threadfin-import.py

echo "3. Mapeando canales nuevos en Threadfin..."
$PYTHON_VENV threadfin-mapping.py

echo "--- Proceso finalizado ---"
