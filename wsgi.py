"""
Fichier WSGI pour PythonAnywhere.

Instructions PythonAnywhere :
1. Dashboard → Web → "WSGI configuration file" → cliquer sur le lien
2. Remplacer tout le contenu par ce fichier
3. Aucune modification nécessaire : les chemins sont calculés automatiquement

Variables d'environnement à définir dans :
Dashboard → Web → "Environment variables" (ou fichier .env sur le serveur) :
  SECRET_KEY   = <valeur secrète longue et aléatoire>
  CORS_ORIGINS = https://rdvaliahnach.netlify.app
  FLASK_DEBUG  = false
  SQLITE_PATH  = (optionnel — par défaut : rdv.db dans le dossier du projet)
"""

import sys
import os

# Chemin absolu vers le dossier du projet, calculé depuis ce fichier.
# Fonctionne quel que soit le nom d'utilisateur PythonAnywhere.
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Charger le .env s'il existe (utile pour les tests sur le serveur)
_env_file = os.path.join(PROJECT_DIR, ".env")
if os.path.isfile(_env_file):
    from dotenv import load_dotenv
    load_dotenv(_env_file, override=False)

# Valeurs par défaut de sécurité minimales si les variables ne sont pas définies.
# En production, ces valeurs DOIVENT être surchargées via les variables d'environnement.
os.environ.setdefault("FLASK_DEBUG", "false")
os.environ.setdefault(
    "CORS_ORIGINS",
    "https://rdvaliahnach.netlify.app"
)
# SQLITE_PATH : si non défini, config.py construit le chemin automatiquement
# depuis le dossier du projet — aucune valeur par défaut nécessaire ici.

from app import create_app

application = create_app()
