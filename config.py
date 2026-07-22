import os
import logging

log = logging.getLogger(__name__)


def _mask(url: str) -> str:
    """Masque le mot de passe dans une URL de connexion pour les logs."""
    try:
        from urllib.parse import urlparse, urlunparse
        p = urlparse(url)
        masked = p._replace(netloc=f"{p.username}:***@{p.hostname}" + (f":{p.port}" if p.port else ""))
        return urlunparse(masked)
    except Exception:
        return "<url invalide>"


def _build_db_uri() -> str:
    # Priorité 1 : DATABASE_URL (Railway l'injecte automatiquement)
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        if url.startswith("mysql://"):
            url = "mysql+pymysql://" + url[len("mysql://"):]
        log.info("[DB] Source        : DATABASE_URL")
        log.info("[DB] URI finale    : %s", _mask(url))
        return url

    # Priorité 2 : MYSQL_URL
    url = os.environ.get("MYSQL_URL", "").strip()
    if url:
        if url.startswith("mysql://"):
            url = "mysql+pymysql://" + url[len("mysql://"):]
        log.info("[DB] Source        : MYSQL_URL")
        log.info("[DB] URI finale    : %s", _mask(url))
        return url

    # Priorité 3 : variables individuelles MYSQL* (Railway MySQL plugin)
    host     = os.environ.get("MYSQLHOST", "").strip()
    port     = os.environ.get("MYSQLPORT", "3306").strip()
    user     = os.environ.get("MYSQLUSER", "").strip()
    password = os.environ.get("MYSQLPASSWORD", "").strip()
    database = os.environ.get("MYSQLDATABASE", "").strip()

    log.info("[DB] MYSQLHOST     : %s", host or "<non défini>")
    log.info("[DB] MYSQLDATABASE : %s", database or "<non défini>")

    if host and user and database:
        url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
        log.info("[DB] Source        : variables MYSQL*")
        log.info("[DB] URI finale    : %s", _mask(url))
        return url

    # Priorité 4 : LOCAL_DATABASE_URL (développement local uniquement)
    url = os.environ.get("LOCAL_DATABASE_URL", "").strip()
    if url:
        log.info("[DB] Source        : LOCAL_DATABASE_URL (dev local)")
        log.info("[DB] URI finale    : %s", _mask(url))
        return url

    log.error("[DB] Aucune variable de base de données trouvée. Vérifiez Railway Variables.")
    return ""


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"
    SQLALCHEMY_DATABASE_URI = _build_db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }