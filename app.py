import os
from flask import Flask
from flask_cors import CORS
from config import Config
from models import db
from routes import api

app = Flask(__name__)
app.config.from_object(Config)
app.register_blueprint(api, url_prefix="/api")

CORS(app)

db.init_app(app)

@app.route("/")
def home():
    return {
        "status": "ok",
        "message": "Backend fonctionne avec MySQL"
    }

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    )