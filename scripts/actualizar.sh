#!/usr/bin/env bash
# Corre todo el proceso de datos de principio a fin.
# Cada paso solo procesa lo nuevo, así que se puede correr todos los días.
#   bash scripts/actualizar.sh
# El paso 6 (Gemini) solo corre si existe la variable GEMINI_API_KEY.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== 1. Inventario de fotos en Drive";      python scripts/01_inventario.py
echo "== 2. Descarga de fotos nuevas";           python scripts/02_descargar.py
echo "== 3. Control de calidad";                 python scripts/03_calidad.py
echo "== 4. Análisis de Gemini de la CGR";       python scripts/04_obrapublica.py
echo "== 5. Detección con modelo abierto";       python scripts/05_deteccion.py
if [ -n "${GEMINI_API_KEY:-}" ]; then
  echo "== 6. Muestra con Gemini (Grupo 3)";     python scripts/06_gemini_muestra.py
else
  echo "== 6. Se omite Gemini: no hay GEMINI_API_KEY"
fi
echo "== 7. Archivo final para la plataforma";  python scripts/07_agregar.py
