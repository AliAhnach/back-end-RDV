from flask import Blueprint, request, jsonify
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import joinedload
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Appointment, Conversation, Message
from datetime import date, datetime

api = Blueprint("api", __name__)
ALLOWED_APPOINTMENT_STATUSES = {"En attente", "Confirmé", "Refusé"}


def get_json_data():
    """Retourne le corps JSON ou None lorsqu'il est absent/invalide."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def serialize_appointment(appointment, include_user_name=False):
    data = {
        "id": appointment.id,
        "service": appointment.service,
        "appointment_date": appointment.appointment_date.strftime("%Y-%m-%d"),
        "appointment_time": appointment.appointment_time.strftime("%H:%M"),
        "description": appointment.description,
        "status": appointment.status,
        "created_at": appointment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": appointment.user_id,
    }

    if include_user_name:
        data["user_name"] = appointment.user.fullname if appointment.user else None

    return data

@api.route("/register", methods=["POST"])
def register():
    data = get_json_data()

    if data is None:
        return jsonify({"success": False, "message": "Le corps de la requête doit être un JSON valide."}), 400

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
        }), 400

    hashed_password = generate_password_hash(password)

    requested_role = (data.get("role") or "user").strip().lower()
    role = requested_role if requested_role in {"user", "admin"} else "user"

    new_user = User(
        fullname=fullname,
        email=email,
        password=hashed_password,
        role=role
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Compte créé avec succès.",
        "user": {
            "id": new_user.id,
            "fullname": new_user.fullname,
            "email": new_user.email,
            "role": new_user.role
        }
    }), 201



@api.route("/login", methods=["POST"])
def login():
    data = get_json_data()

    if data is None:
        return jsonify({"success": False, "message": "Le corps de la requête doit être un JSON valide."}), 400

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
        }), 400

    return jsonify({
        "success": True,
        "message": "Connexion réussie.",
        "user": {
            "id": user.id,
            "fullname": user.fullname,
            "email": user.email,
            "role": user.role
        }
    }), 200

@api.route("/appointments", methods=["POST"])
def create_appointment():
    data = get_json_data()

    if data is None:
        return jsonify({"success": False, "message": "Le corps de la requête doit être un JSON valide."}), 400

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
        user_id = int(user_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "L'identifiant utilisateur est invalide."}), 400

    if not User.query.get(user_id):
        return jsonify({"success": False, "message": "Utilisateur introuvable."}), 404

    try:
        parsed_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
        parsed_time = datetime.strptime(appointment_time, "%H:%M").time()
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "message": "La date ou l'heure est invalide (formats attendus : YYYY-MM-DD et HH:MM)."
        }), 400

    try:
        new_appointment = Appointment(
            service=service,
            appointment_date=parsed_date,
            appointment_time=parsed_time,
            description=description,
            status="En attente",
            user_id=user_id
        )

        db.session.add(new_appointment)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Rendez-vous créé avec succès.",
            "appointment": serialize_appointment(new_appointment)
        }), 201

    except Exception:
        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Une erreur est survenue lors de la création du rendez-vous."
        }), 500


def appointments_response(appointments):
    return jsonify({
        "success": True,
        "appointments": [
            serialize_appointment(appointment, include_user_name=True)
            for appointment in appointments
        ]
    }), 200


@api.route("/appointments", methods=["GET"])
def get_all_appointments():
    appointments = Appointment.query.options(
        joinedload(Appointment.user)
    ).order_by(Appointment.id).all()
    return appointments_response(appointments)


@api.route("/appointments/<int:user_id>", methods=["GET"])
def get_appointments(user_id):
    if not User.query.get(user_id):
        return jsonify({"success": False, "message": "Utilisateur introuvable."}), 404

    appointments = Appointment.query.options(
        joinedload(Appointment.user)
    ).filter_by(user_id=user_id).order_by(Appointment.id).all()
    return appointments_response(appointments)


@api.route("/appointments/<int:appointment_id>", methods=["PUT"])
def update_appointment_status(appointment_id):
    data = get_json_data()

    if data is None:
        return jsonify({"success": False, "message": "Le corps de la requête doit être un JSON valide."}), 400

    if set(data) != {"status"}:
        return jsonify({
            "success": False,
            "message": "Seul le champ 'status' peut être modifié."
        }), 400

    status = data.get("status")
    if status not in ALLOWED_APPOINTMENT_STATUSES:
        return jsonify({
            "success": False,
            "message": "Statut invalide. Valeurs autorisées : En attente, Confirmé, Refusé."
        }), 400

    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return jsonify({"success": False, "message": "Rendez-vous introuvable."}), 404

    try:
        appointment.status = status
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "Une erreur est survenue lors de la mise à jour du rendez-vous."
        }), 500

    return jsonify({
        "success": True,
        "message": "Statut du rendez-vous mis à jour avec succès.",
        "appointment": serialize_appointment(appointment)
    }), 200


@api.route("/appointments/<int:appointment_id>", methods=["DELETE"])
def delete_appointment(appointment_id):
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return jsonify({
            "success": False,
            "message": "Rendez-vous introuvable."
        }), 404

    try:
        db.session.delete(appointment)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "Une erreur est survenue lors de la suppression du rendez-vous."
        }), 500

    return jsonify({
        "success": True,
        "message": "Rendez-vous supprimé avec succès."
    }), 200


@api.route("/dashboard/stats", methods=["GET"])
def get_dashboard_stats():
    today = date.today()
    month_start = today.replace(day=1)
    next_month_start = (
        date(today.year + 1, 1, 1)
        if today.month == 12
        else date(today.year, today.month + 1, 1)
    )

    try:
        appointment_counts = db.session.query(
            func.count(Appointment.id).label("appointments"),
            func.coalesce(
                func.sum(case((Appointment.status == "En attente", 1), else_=0)), 0
            ).label("waiting"),
            func.coalesce(
                func.sum(case((Appointment.status == "Confirmé", 1), else_=0)), 0
            ).label("confirmed"),
            func.coalesce(
                func.sum(case((Appointment.status == "Refusé", 1), else_=0)), 0
            ).label("refused"),
            func.coalesce(
                func.sum(case((Appointment.appointment_date == today, 1), else_=0)), 0
            ).label("today"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (Appointment.appointment_date >= month_start)
                            & (Appointment.appointment_date < next_month_start),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("this_month"),
        ).one()

        recent_appointments = Appointment.query.options(
            joinedload(Appointment.user)
        ).order_by(
            Appointment.created_at.desc(), Appointment.id.desc()
        ).limit(5).all()

        return jsonify({
            "success": True,
            "stats": {
                "users": User.query.count(),
                "appointments": int(appointment_counts.appointments or 0),
                "waiting": int(appointment_counts.waiting or 0),
                "confirmed": int(appointment_counts.confirmed or 0),
                "refused": int(appointment_counts.refused or 0),
                "today": int(appointment_counts.today or 0),
                "this_month": int(appointment_counts.this_month or 0),
                "recent": [
                    {
                        "id": appointment.id,
                        "service": appointment.service,
                        "appointment_date": appointment.appointment_date.strftime("%Y-%m-%d"),
                        "appointment_time": appointment.appointment_time.strftime("%H:%M"),
                        "status": appointment.status,
                        "fullname": appointment.user.fullname if appointment.user else None,
                    }
                    for appointment in recent_appointments
                ],
            },
        }), 200
    except Exception:
        return jsonify({
            "success": False,
            "message": "Une erreur est survenue lors de la récupération des statistiques."
        }), 500


@api.route("/dashboard/user/<int:user_id>", methods=["GET"])
def get_user_dashboard_stats(user_id):
    if not db.session.get(User, user_id):
        return jsonify({"success": False, "message": "Utilisateur introuvable."}), 404

    now = datetime.now()
    today = now.date()
    current_time = now.time()

    try:
        appointment_counts = db.session.query(
            func.count(Appointment.id).label("total_appointments"),
            func.coalesce(
                func.sum(case((Appointment.status == "En attente", 1), else_=0)), 0
            ).label("waiting"),
            func.coalesce(
                func.sum(case((Appointment.status == "Confirmé", 1), else_=0)), 0
            ).label("confirmed"),
            func.coalesce(
                func.sum(case((Appointment.status == "Refusé", 1), else_=0)), 0
            ).label("refused"),
        ).filter(Appointment.user_id == user_id).one()

        next_appointment = Appointment.query.filter(
            Appointment.user_id == user_id,
            or_(
                Appointment.appointment_date > today,
                and_(
                    Appointment.appointment_date == today,
                    Appointment.appointment_time >= current_time,
                ),
            ),
        ).order_by(
            Appointment.appointment_date,
            Appointment.appointment_time,
            Appointment.id,
        ).first()

        recent_appointments = Appointment.query.filter_by(
            user_id=user_id
        ).order_by(
            Appointment.created_at.desc(), Appointment.id.desc()
        ).limit(5).all()

        def dashboard_appointment(appointment):
            if not appointment:
                return None

            return {
                "id": appointment.id,
                "service": appointment.service,
                "appointment_date": appointment.appointment_date.strftime("%Y-%m-%d"),
                "appointment_time": appointment.appointment_time.strftime("%H:%M"),
                "status": appointment.status,
            }

        return jsonify({
            "success": True,
            "stats": {
                "total_appointments": int(appointment_counts.total_appointments or 0),
                "waiting": int(appointment_counts.waiting or 0),
                "confirmed": int(appointment_counts.confirmed or 0),
                "refused": int(appointment_counts.refused or 0),
                "next_appointment": dashboard_appointment(next_appointment),
                "recent_appointments": [
                    dashboard_appointment(appointment)
                    for appointment in recent_appointments
                ],
            },
        }), 200
    except Exception:
        return jsonify({
            "success": False,
            "message": "Une erreur est survenue lors de la récupération des statistiques utilisateur."
        }), 500


# ---------------------------------------------------------------------------
# Messagerie interne (conversations)
# ---------------------------------------------------------------------------

def serialize_message(message):
    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "sender_name": message.sender.fullname if message.sender else None,
        "sender_role": message.sender.role if message.sender else None,
        "content": message.content,
        "created_at": message.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    }


def serialize_conversation(conv):
    return {
        "id": conv.id,
        "subject": conv.subject,
        "is_read": conv.is_read,
        "created_at": conv.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "sender": {
            "id": conv.user.id,
            "fullname": conv.user.fullname,
        } if conv.user else None,
        "messages": [serialize_message(m) for m in conv.messages],
    }


@api.route("/messages", methods=["POST"])
def send_message():
    data = get_json_data()
    if data is None:
        return jsonify({"success": False, "message": "JSON invalide."}), 400

    sender_id = data.get("sender_id")
    content = (data.get("content") or "").strip()

    if not sender_id or not content:
        return jsonify({"success": False, "message": "Les champs sender_id et content sont obligatoires."}), 400

    sender = db.session.get(User, sender_id)
    if not sender:
        return jsonify({"success": False, "message": "Expéditeur introuvable."}), 404

    admin = User.query.filter_by(role="admin").first()
    if not admin:
        return jsonify({"success": False, "message": "Aucun administrateur disponible."}), 404

    try:
        conv = Conversation(user_id=sender_id, admin_id=admin.id)
        db.session.add(conv)
        db.session.flush()

        msg = Message(conversation_id=conv.id, sender_id=sender_id, content=content)
        db.session.add(msg)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "Erreur lors de la création de la conversation."}), 500

    return jsonify({"success": True, "data": serialize_conversation(conv)}), 201


@api.route("/messages/user/<int:user_id>", methods=["GET"])
def get_user_messages(user_id):
    if not db.session.get(User, user_id):
        return jsonify({"success": False, "message": "Utilisateur introuvable."}), 404

    conversations = Conversation.query.filter_by(
        user_id=user_id
    ).order_by(Conversation.created_at.desc()).all()

    return jsonify({"success": True, "data": [serialize_conversation(c) for c in conversations]}), 200


@api.route("/messages/admin", methods=["GET"])
def get_admin_messages():
    conversations = Conversation.query.order_by(
        Conversation.created_at.desc()
    ).all()

    return jsonify({"success": True, "data": [serialize_conversation(c) for c in conversations]}), 200


@api.route("/messages/<int:conversation_id>/reply", methods=["POST"])
def reply_to_message(conversation_id):
    conv = db.session.get(Conversation, conversation_id)
    if not conv:
        return jsonify({"success": False, "message": "Conversation introuvable."}), 404

    data = get_json_data()
    if data is None:
        return jsonify({"success": False, "message": "JSON invalide."}), 400

    sender_id = data.get("sender_id")
    content = (data.get("content") or "").strip()

    if not sender_id or not content:
        return jsonify({"success": False, "message": "Les champs sender_id et content sont obligatoires."}), 400

    sender = db.session.get(User, sender_id)
    if not sender:
        return jsonify({"success": False, "message": "Expéditeur introuvable."}), 404

    try:
        msg = Message(conversation_id=conv.id, sender_id=sender_id, content=content)
        db.session.add(msg)
        if sender.role == "user":
            conv.is_read = False
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "Erreur lors de l'envoi de la réponse."}), 500

    return jsonify({"success": True, "data": serialize_conversation(conv)}), 200


@api.route("/messages/<int:conversation_id>/read", methods=["PUT"])
def mark_message_read(conversation_id):
    conv = db.session.get(Conversation, conversation_id)
    if not conv:
        return jsonify({"success": False, "message": "Conversation introuvable."}), 404

    try:
        conv.is_read = True
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "Erreur lors de la mise à jour."}), 500

    return jsonify({"success": True}), 200
