import os


def _build_db_uri():
    # Priorité 1 : DATABASE_URL fournie directement (Railway l'injecte automatiquement)
    url = os.environ.get("DATABASE_URL", "")
    if url:
        if url.startswith("mysql://"):
            url = "mysql+pymysql://" + url[len("mysql://"):]
        return url

    # Priorité 2 : variables individuelles MYSQL* (Railway MySQL plugin)
    host = os.environ.get("MYSQLHOST")
    port = os.environ.get("MYSQLPORT", "3306")
    user = os.environ.get("MYSQLUSER")
    password = os.environ.get("MYSQLPASSWORD", "")
    database = os.environ.get("MYSQLDATABASE")

    if host and user and database:
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"

    # Priorité 3 : fallback local pour le développement uniquement
    return os.environ.get(
        "LOCAL_DATABASE_URL",
        "mysql+pymysql://rdv_user:rdv_password@localhost/rdv_db"
    )


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"
    SQLALCHEMY_DATABASE_URI = _build_db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }