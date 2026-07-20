from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User

api = Blueprint("api", __name__)

@api.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    fullname = data.get("fullname")
    email = data.get("email")
    password = data.get("password")

    if not fullname or not email or not password:
        return jsonify({
            "success": False,
            "message": "Tous les champs sont obligatoires."
        }), 400

    user = User.query.filter_by(email=email).first()

    if user:
        return jsonify({
            "success": False,
            "message": "Cet email existe déjà."
        }), 409

    hashed_password = generate_password_hash(password)

    new_user = User(
        fullname=fullname,
        email=email,
        password=hashed_password
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Compte créé avec succès."
    }), 201



@api.route("/login", methods=["POST"])
def login():

    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Email et mot de passe obligatoires."
        }), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({
            "success": False,
            "message": "Utilisateur introuvable."
        }), 404

    if not check_password_hash(user.password, password):
        return jsonify({
            "success": False,
            "message": "Mot de passe incorrect."
        }), 401

    return jsonify({
        "success": True,
        "message": "Connexion réussie.",
        "user": {
            "id": user.id,
            "fullname": user.fullname,
            "email": user.email
        }
    }), 200