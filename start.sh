#!/bin/bash
# Lance le backend Flask en local avec le virtualenv
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Crée le venv si absent
if [ ! -d ".venv" ]; then
  echo "📦 Création du virtualenv..."
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt -q
  echo "✅ Dépendances installées"
fi

echo "🚀 Backend Flask → http://127.0.0.1:5000"
echo "   CORS autorisé pour : localhost:5500, localhost:5501, localhost:3000"
echo "   Arrêt : Ctrl+C"
echo ""

.venv/bin/python3 app.py
