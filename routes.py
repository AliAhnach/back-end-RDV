from flask import Blueprint

api = Blueprint("api", __name__)

@api.route("/login", methods=["POST"])
def login():
    return {
        "message": "Connexion réussie"
    }

@api.route("/register", methods=["POST"])
def register():
    return {
        "message": "Compte créé"
    }