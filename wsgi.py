"""
Fichier WSGI pour PythonAnywhere (SQLite).

Instructions :
1. Dashboard PythonAnywhere → Web → WSGI configuration file
2. Remplacer le contenu par ce fichier
3. Adapter "votre_username" avec votre nom d'utilisateur PythonAnywhere
"""

import sys
import os

# Chemin vers le projet — adapter avec votre nom d'utilisateur
CHEMIN_PROJET = "/home/votre_username/backend"

if CHEMIN_PROJET not in sys.path:
    sys.path.insert(0, CHEMIN_PROJET)

# Variables d'environnement
os.environ.setdefault("SECRET_KEY", "changez-cette-valeur-en-production")
os.environ.setdefault("CORS_ORIGINS", "https://rdvaliahnach.netlify.app")

# SQLite : chemin absolu vers le fichier de base de données
# PythonAnywhere : utiliser un chemin dans le home directory
os.environ.setdefault(
    "SQLITE_PATH",
    "/home/votre_username/backend/rdv.db"
)

from app import create_app

application = create_app()
