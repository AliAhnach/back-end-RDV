import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://rdv_user:123456@localhost/rdv_db"
    )

    if SQLALCHEMY_DATABASE_URI.startswith("mysql://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "mysql://",
            "mysql+pymysql://",
            1
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False