from flask import Blueprint, request, jsonify, session
from functools import wraps
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import joinedload
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Appointment, Conversation, Message
from datetime import date, datetime

api = Blueprint("api", __name__)
ALLOWED_APPOINTMENT_STATUSES = {"En attente", "Confirmé", "Refusé"}
ALLOWED_ROLES = {"user", "admin"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_json_data():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    if not user or user.role not in ALLOWED_ROLES:
        session.clear()
        return None
    return user


def _resolve_user(user_id_from_request):
    """Retourne l'utilisateur depuis la session ou depuis un user_id explicite."""
    user = get_current_user()
    if user:
        return user
    if user_id_from_request:
        try:
            return db.session.get(User, int(user_id_from_request))
        except (TypeError, ValueError):
            return None
    return None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            return jsonify({"success": False, "message": "Authentication required."}), 401
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"success": False, "message": "Authentication required."}), 401
        if user.role != "admin":
            return jsonify({"success": False, "message": "Admin access required."}), 403
        return view(*args, **kwargs)
    return wrapped


def serialize_user(user):
    return {
        "id": user.id,
        "fullname": user.fullname,
        "email": user.email,
        "role": user.role,
        "profile_image": user.profile_image,
    }


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


def appointments_response(appointments):
    return jsonify({
        "success": True,
        "appointments": [serialize_appointment(a, include_user_name=True) for a in appointments]
    }), 200


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@api.route("/register", methods=["POST"])
def register():
    data = get_json_data()
    if data is None:
        return jsonify({"success": False, "message": "Le corps de la requête doit être un JSON valide."}), 400

    fullname = data.get("fullname")
    email = data.get("email")
    password = data.get("password")

    if not fullname or not email or not password:
        return jsonify({"success": False, "message": "Tous les champs sont obligatoires."}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "message": "Cet email existe déjà."}), 400

    new_user = User(
        fullname=fullname,
        email=email,
        password=generate_password_hash(password),
        role="user",
        profile_image=None,
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"success": True, "message": "Compte créé avec succès.", "user": serialize_user(new_user)}), 201


@api.route("/login", methods=["POST"])
def login():
    data = get_json_data()
    if data is None:
        return jsonify({"success": False, "message": "Le corps de la requête doit être un JSON valide."}), 400

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"success": False, "message": "Email et mot de passe obligatoires."}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"success": False, "message": "Utilisateur introuvable."}), 404

    if not check_password_hash(user.password, password):
        return jsonify({"success": False, "message": "Mot de passe incorrect."}), 400

    if user.role not in ALLOWED_ROLES:
        return jsonify({"success": False, "message": "Rôle invalide."}), 403

    session.clear()
    session["user_id"] = user.id

    return jsonify({"success": True, "message": "Connexion réussie.", "user": serialize_user(user)}), 200


@api.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Déconnexion réussie."}), 200


# ---------------------------------------------------------------------------
# Profil
# ---------------------------------------------------------------------------

@api.route("/profile", methods=["GET"])
def get_profile():
    user = _resolve_user(request.args.get("user_id"))
    if not user:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    return jsonify({"success": True, "user": serialize_user(user)}), 200


@api.route("/profile", methods=["PUT"])
@login_required
def update_profile():
    data = get_json_data()
    if data is None or set(data) != {"profile_image"}:
        return jsonify({"success": False, "message": "Seul le champ 'profile_image' peut être modifié."}), 400

    profile_image = data["profile_image"]
    if profile_image is not None:
        if not isinstance(profile_image, str):
            return jsonify({"success": False, "message": "L'image de profil est invalide."}), 400
        profile_image = profile_image.strip() or None
        if profile_image and len(profile_image) > 500:
            return jsonify({"success": False, "message": "L'image de profil est trop longue."}), 400

    user = get_current_user()
    try:
        user.profile_image = profile_image
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "Erreur lors de la mise à jour du profil."}), 500

    return jsonify({"success": True, "user": serialize_user(user)}), 200


# ---------------------------------------------------------------------------
# Rendez-vous — utilisateur
# ---------------------------------------------------------------------------

@api.route("/appointments", methods=["POST"])
def create_appointment():
    data = get_json_data()
    if data is None:
        return jsonify({"success": False, "message": "Le corps de la requête doit être un JSON valide."}), 400

    service = data.get("service")
    appointment_date = data.get("appointment_date") or data.get("date")
    appointment_time = data.get("appointment_time") or data.get("time")
    description = data.get("description")

    user = _resolve_user(data.get("user_id"))
    if not user:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    if not all([service, appointment_date, appointment_time]):
        return jsonify({"success": False, "message": "Tous les champs obligatoires doivent être remplis."}), 400

    try:
        parsed_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
        parsed_time = datetime.strptime(appointment_time, "%H:%M").time()
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Date ou heure invalide (YYYY-MM-DD et HH:MM)."}), 400

    try:
        appt = Appointment(
            service=service,
            appointment_date=parsed_date,
            appointment_time=parsed_time,
            description=description,
            status="En attente",
            user_id=user.id,
        )
        db.session.add(appt)
        db.session.commit()
        return jsonify({"success": True, "message": "Rendez-vous créé avec succès.", "appointment": serialize_appointment(appt)}), 201
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "Erreur lors de la création du rendez-vous."}), 500


@api.route("/appointments", methods=["GET"])
def get_current_user_appointments():
    """Rendez-vous de l'utilisateur connecté (session ou ?user_id=)."""
    user = _resolve_user(request.args.get("user_id"))
    if not user:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    appointments = Appointment.query.options(
        joinedload(Appointment.user)
    ).filter_by(user_id=user.id).order_by(Appointment.id).all()
    return appointments_response(appointments)


@api.route("/appointments/<int:appointment_id>", methods=["DELETE"])
def delete_appointment(appointment_id):
    appt = Appointment.query.get(appointment_id)
    if not appt:
        return jsonify({"success": False, "message": "Rendez-vous introuvable."}), 404

    user = _resolve_user(request.args.get("user_id"))
    if not user:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    if appt.user_id != user.id and user.role != "admin":
        return jsonify({"success": False, "message": "Accès non autorisé."}), 403

    try:
        db.session.delete(appt)
        db.session.commit()
        return jsonify({"success": True, "message": "Rendez-vous supprimé avec succès."}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "Erreur lors de la suppression."}), 500


# ---------------------------------------------------------------------------
# Rendez-vous — admin
# ---------------------------------------------------------------------------

@api.route("/admin/appointments", methods=["GET"])
def get_admin_appointments():
    """Tous les rendez-vous — accessible par session admin OU sans auth (fallback frontend)."""
    appointments = Appointment.query.options(
        joinedload(Appointment.user)
    ).order_by(Appointment.id).all()
    return appointments_response(appointments)


@api.route("/admin/appointments/<int:appointment_id>/status", methods=["PUT"])
def update_admin_appointment_status(appointment_id):
    data = get_json_data()
    if data is None:
        return jsonify({"success": False, "message": "Le corps de la requête doit être un JSON valide."}), 400

    if set(data) - {"status", "user_id"} or "status" not in data:
        return jsonify({"success": False, "message": "Seul le champ 'status' peut être modifié."}), 400

    status = data.get("status")
    if status not in ALLOWED_APPOINTMENT_STATUSES:
        return jsonify({"success": False, "message": "Statut invalide. Valeurs autorisées : En attente, Confirmé, Refusé."}), 400

    appt = Appointment.query.get(appointment_id)
    if not appt:
        return jsonify({"success": False, "message": "Rendez-vous introuvable."}), 404

    try:
        appt.status = status
        db.session.commit()
        return jsonify({"success": True, "message": "Statut mis à jour.", "appointment": serialize_appointment(appt)}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "Erreur lors de la mise à jour."}), 500


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@api.route("/dashboard/stats", methods=["GET"])
def get_dashboard_stats():
    today = date.today()
    month_start = today.replace(day=1)
    next_month_start = (
        date(today.year + 1, 1, 1) if today.month == 12
        else date(today.year, today.month + 1, 1)
    )

    try:
        counts = db.session.query(
            func.count(Appointment.id).label("appointments"),
            func.coalesce(func.sum(case((Appointment.status == "En attente", 1), else_=0)), 0).label("waiting"),
            func.coalesce(func.sum(case((Appointment.status == "Confirmé", 1), else_=0)), 0).label("confirmed"),
            func.coalesce(func.sum(case((Appointment.status == "Refusé", 1), else_=0)), 0).label("refused"),
            func.coalesce(func.sum(case((Appointment.appointment_date == today, 1), else_=0)), 0).label("today"),
            func.coalesce(func.sum(case(
                ((Appointment.appointment_date >= month_start) & (Appointment.appointment_date < next_month_start), 1),
                else_=0,
            )), 0).label("this_month"),
        ).one()

        recent = Appointment.query.options(joinedload(Appointment.user)).order_by(
            Appointment.created_at.desc(), Appointment.id.desc()
        ).limit(5).all()

        return jsonify({
            "success": True,
            "stats": {
                "users": User.query.count(),
                "appointments": int(counts.appointments or 0),
                "waiting": int(counts.waiting or 0),
                "confirmed": int(counts.confirmed or 0),
                "refused": int(counts.refused or 0),
                "today": int(counts.today or 0),
                "this_month": int(counts.this_month or 0),
                "recent": [
                    {
                        "id": a.id,
                        "service": a.service,
                        "appointment_date": a.appointment_date.strftime("%Y-%m-%d"),
                        "appointment_time": a.appointment_time.strftime("%H:%M"),
                        "status": a.status,
                        "fullname": a.user.fullname if a.user else None,
                    }
                    for a in recent
                ],
            },
        }), 200
    except Exception:
        return jsonify({"success": False, "message": "Erreur lors de la récupération des statistiques."}), 500


@api.route("/dashboard/user/<int:user_id>", methods=["GET"])
def get_user_dashboard_stats(user_id):
    if not db.session.get(User, user_id):
        return jsonify({"success": False, "message": "Utilisateur introuvable."}), 404

    now = datetime.now()
    today = now.date()

    try:
        counts = db.session.query(
            func.count(Appointment.id).label("total_appointments"),
            func.coalesce(func.sum(case((Appointment.status == "En attente", 1), else_=0)), 0).label("waiting"),
            func.coalesce(func.sum(case((Appointment.status == "Confirmé", 1), else_=0)), 0).label("confirmed"),
            func.coalesce(func.sum(case((Appointment.status == "Refusé", 1), else_=0)), 0).label("refused"),
        ).filter(Appointment.user_id == user_id).one()

        next_appt = Appointment.query.filter(
            Appointment.user_id == user_id,
            or_(
                Appointment.appointment_date > today,
                and_(Appointment.appointment_date == today, Appointment.appointment_time >= now.time()),
            ),
        ).order_by(Appointment.appointment_date, Appointment.appointment_time, Appointment.id).first()

        recent = Appointment.query.filter_by(user_id=user_id).order_by(
            Appointment.created_at.desc(), Appointment.id.desc()
        ).limit(5).all()

        def fmt(a):
            if not a:
                return None
            return {
                "id": a.id, "service": a.service,
                "appointment_date": a.appointment_date.strftime("%Y-%m-%d"),
                "appointment_time": a.appointment_time.strftime("%H:%M"),
                "status": a.status,
            }

        return jsonify({
            "success": True,
            "stats": {
                "total_appointments": int(counts.total_appointments or 0),
                "waiting": int(counts.waiting or 0),
                "confirmed": int(counts.confirmed or 0),
                "refused": int(counts.refused or 0),
                "next_appointment": fmt(next_appt),
                "recent_appointments": [fmt(a) for a in recent],
            },
        }), 200
    except Exception:
        return jsonify({"success": False, "message": "Erreur lors de la récupération des statistiques utilisateur."}), 500


# ---------------------------------------------------------------------------
# Messagerie interne
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
        "sender": {"id": conv.user.id, "fullname": conv.user.fullname} if conv.user else None,
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
    conversations = Conversation.query.order_by(Conversation.created_at.desc()).all()
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
