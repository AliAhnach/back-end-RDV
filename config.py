import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key")
    _db_url = os.environ.get("DATABASE_URL", "mysql+pymysql://rdv_user:motdepasse@localhost/rdv_db")
    SQLALCHEMY_DATABASE_URI = _db_url.replace("mysql://", "mysql+pymysql://", 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False