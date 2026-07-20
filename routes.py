from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Appointment

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

from datetime import datetime


@api.route("/appointments", methods=["POST"])
def create_appointment():

    data = request.get_json()

    service = data.get("service")
    appointment_date = data.get("appointment_date")
    appointment_time = data.get("appointment_time")
    description = data.get("description")
    user_id = data.get("user_id")

    if not all([service, appointment_date, appointment_time, user_id]):
        return jsonify({
            "success": False,
            "message": "Tous les champs obligatoires doivent être remplis."
        }), 400

    try:
        new_appointment = Appointment(
            service=service,
            appointment_date=datetime.strptime(
                appointment_date,
                "%Y-%m-%d"
            ).date(),
            appointment_time=datetime.strptime(
                appointment_time,
                "%H:%M"
            ).time(),
            description=description,
            status="En attente",
            user_id=user_id
        )

        db.session.add(new_appointment)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Rendez-vous créé avec succès."
        }), 201

    except Exception as e:
        db.session.rollback()

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
    
@api.route("/appointments/<int:user_id>", methods=["GET"])
def get_appointments(user_id):

    appointments = Appointment.query.filter_by(user_id=user_id).all()

    data = []

    for appointment in appointments:
        data.append({
            "id": appointment.id,
            "service": appointment.service,
            "appointment_date": appointment.appointment_date.strftime("%Y-%m-%d"),
            "appointment_time": appointment.appointment_time.strftime("%H:%M"),
            "description": appointment.description,
            "status": appointment.status,
            "created_at": appointment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": appointment.user_id
        })

    return jsonify({
        "success": True,
        "appointments": data
    }), 200