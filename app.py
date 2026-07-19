import os
from flask import Flask
from flask_cors import CORS
from config import Config
from models import db
from routes import api

# --- DEBUG TEMPORAIRE ---
_raw = os.environ.get("DATABASE_URL")
print("[DEBUG] DATABASE_URL brute :", _raw)
print("[DEBUG] URI finale         :", Config.SQLALCHEMY_DATABASE_URI)
# --- FIN DEBUG ---

app = Flask(__name__)
app.config.from_object(Config)

CORS(app, origins=["https://rdvaliahnach.netlify.app"])

db.init_app(app)
app.register_blueprint(api, url_prefix="/api")

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)