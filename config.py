import os
print("DATABASE_URL =", os.environ.get("DATABASE_URL"))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key")
    _db_url = os.environ.get("DATABASE_URL", "")
    if _db_url.startswith("mysql://"):
        _db_url = "mysql+pymysql://" + _db_url[len("mysql://"):]
    elif not _db_url.startswith("mysql+pymysql://"):
        _db_url = ""
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False