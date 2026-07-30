import os
import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)
from dotenv import load_dotenv
load_dotenv(override=False)
from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import event
from sqlalchemy.engine import Engine
from config import Config
from models import db, User
from routes import api


def _seed_admin():
    """Crée le compte admin par défaut s'il n'existe pas."""
    if not User.query.filter_by(email="admin@gmail.com").first():
        from werkzeug.security import generate_password_hash
        admin = User(
            fullname="admin",
            email="admin@gmail.com",
            password=generate_password_hash("0000"),
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()
        logging.getLogger(__name__).info("[SEED] Compte admin créé.")


# SQLite désactive les foreign keys par défaut — on les active à chaque connexion
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in type(dbapi_connection).__module__:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Configuration des cookies de session pour le développement cross-origin (local)
    # et la production (HTTPS). Le navigateur n'enverra pas le cookie
    # de session sans ces paramètres stricts.
    app.config.update(
        SESSION_COOKIE_SAMESITE='None',
        SESSION_COOKIE_SECURE=True
    )

    # Récupère les origines de production depuis la variable d'environnement
    raw_origins = os.environ.get(
        "CORS_ORIGINS",
        "https://rdvaliahnach.netlify.app"
    )
    allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

    # En mode debug local ou si le backend doit autoriser explicitement localhost.
    is_debug = str(os.environ.get("FLASK_DEBUG", "false")).lower() == "true"
    allow_localhost = str(os.environ.get("ALLOW_LOCALHOST_CORS", "false")).lower() == "true"
    if is_debug or allow_localhost:
        local_dev_origins = [
            "http://localhost:5500", "http://127.0.0.1:5500",
            "http://localhost:5173", "http://127.0.0.1:5173",
            "http://localhost:8080", "http://127.0.0.1:8080",
            "http://localhost:3000", "http://127.0.0.1:3000",
        ]
        allowed_origins.extend([o for o in local_dev_origins if o not in allowed_origins])

    log.info("[CORS] Origines autorisées : %s", allowed_origins)
    CORS(app,
         origins=allowed_origins,
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization"],
         supports_credentials=True)

    db.init_app(app)
    app.register_blueprint(api, url_prefix="/api")

    with app.app_context():
        db.create_all()
        _seed_admin()

    @app.route("/")
    def home():
        return jsonify({"status": "ok", "message": "Backend opérationnel"})

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "message": "Health check OK"})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    )
