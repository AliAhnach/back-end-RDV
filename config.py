class Config:
    SECRET_KEY = "change-this-secret-key"
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://rdv_user:motdepasse@localhost/rdv_db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False