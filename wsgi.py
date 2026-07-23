"""
Fichier WSGI pour PythonAnywhere.

Instructions de déploiement :
1. Dans le dashboard PythonAnywhere → Web → WSGI configuration file
2. Remplacer le contenu par ce fichier
3. Adapter CHEMIN_PROJET avec votre nom d'utilisateur PythonAnywhere
   Exemple : /home/votre_username/backend
"""

import sys
import os

# --- Chemin vers le projet ---
# Remplacer "votre_username" par votre nom d'utilisateur PythonAnywhere
CHEMIN_PROJET = "/home/votre_username/backend"

if CHEMIN_PROJET not in sys.path:
    sys.path.insert(0, CHEMIN_PROJET)

# --- Variables d'environnement ---
# Définir ici toutes les variables nécessaires
# (ou les configurer dans l'onglet "Web" > "Environment variables" de PythonAnywhere)
os.environ.setdefault("SECRET_KEY", "changez-cette-valeur-en-production")
os.environ.setdefault("CORS_ORIGINS", "https://rdvaliahnach.netlify.app")

# Base de données MySQL PythonAnywhere
# Format : mysql+pymysql://username:password@username.mysql.pythonanywhere-services.com/username$dbname
os.environ.setdefault(
    "DATABASE_URL",
    "mysql+pymysql://votre_username:votre_password@votre_username.mysql.pythonanywhere-services.com/votre_username$rdv_db"
)

# --- Import de l'application ---
from app import create_app

application = create_app()
