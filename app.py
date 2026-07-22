import os
import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from models import db
from routes import api

app = Flask(__name__)
app.config.from_object(Config)

allowed_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500"
).split(",")

CORS(app, origins=[o.strip() for o in allowed_origins])

db.init_app(app)
app.register_blueprint(api, url_prefix="/api")

with app.app_context():
    db.create_all()


@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "Backend fonctionne avec MySQL"})


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    )