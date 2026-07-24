import os
import logging

log = logging.getLogger(__name__)


def _build_db_uri() -> str:
    # Priorité 1 : DATABASE_URL explicite (SQLite ou autre)
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        log.info("[DB] Source : DATABASE_URL — %s", url)
        return url

    # Priorité 2 : chemin SQLite personnalisé
    sqlite_path = os.environ.get("SQLITE_PATH", "").strip()
    if sqlite_path:
        uri = f"sqlite:///{sqlite_path}"
        log.info("[DB] Source : SQLITE_PATH — %s", uri)
        return uri

    # Priorité 3 : fichier SQLite par défaut dans le dossier du projet
    base_dir = os.path.abspath(os.path.dirname(__file__))
    default_path = os.path.join(base_dir, "rdv.db")
    uri = f"sqlite:///{default_path}"
    log.info("[DB] Source : SQLite par défaut — %s", uri)
    return uri


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"
    SQLALCHEMY_DATABASE_URI = _build_db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
