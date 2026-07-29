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

echo "🚀 Backend Flask prêt"
echo "   CORS de production : https://rdvaliahnach.netlify.app"
echo "   Arrêt : Ctrl+C"
echo ""

.venv/bin/python3 app.py
