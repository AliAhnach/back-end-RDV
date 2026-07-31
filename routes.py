import logging
log = logging.getLogger(__name__)

from io import BytesIO
from flask import Blueprint, request, jsonify, session, make_response
from functools import wraps
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import joinedload, subqueryload
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
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


def _generate_appointment_receipt_pdf(appointment, admin_name):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 34
    header_color = colors.HexColor('#1f5fbf')
    accent_blue = colors.HexColor('#2f6ce4')
    text_dark = colors.HexColor('#11254a')
    text_gray = colors.HexColor('#58607c')
    card_bg = colors.HexColor('#f4f7fb')
    section_line = colors.HexColor('#d9e2ef')
    success = colors.HexColor('#22a55f')
    warning = colors.HexColor('#f59e0b')
    danger = colors.HexColor('#dc2626')

    receipt_number = f"RDV-{appointment.id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    generated_at = datetime.utcnow().strftime('%d/%m/%Y %H:%M')
    appointment_date = appointment.appointment_date.strftime('%d/%m/%Y') if appointment.appointment_date else '—'
    appointment_time = appointment.appointment_time.strftime('%H:%M') if appointment.appointment_time else '—'
    confirmation_date = appointment.created_at.strftime('%d/%m/%Y') if appointment.created_at else '—'
    user_name = appointment.user.fullname if appointment.user else 'Utilisateur'
    user_email = appointment.user.email if appointment.user else '—'
    appointment_type = appointment.service or '—'
    appointment_status = appointment.status or '—'

    status_color = {
        'Confirmé': success,
        'En attente': warning,
        'Refusé': danger,
    }.get(appointment_status, accent_blue)

    # Page border for a polished finish
    c.setStrokeColor(section_line)
    c.setLineWidth(1)
    c.roundRect(margin / 2, margin / 2, width - margin, height - margin, 18, stroke=1, fill=0)

    # Subtle watermark
    c.saveState()
    c.setFillColor(colors.HexColor('#eef4fd'))
    c.setFont('Helvetica-Bold', 68)
    c.translate(width * 0.15, height * 0.55)
    c.rotate(45)
    c.drawCentredString(width * 0.25, 0, 'RDV')
    c.restoreState()

    # Header
    header_height = 140
    c.setFillColor(header_color)
    c.roundRect(margin, height - margin - header_height, width - 2 * margin, header_height, 16, stroke=0, fill=1)

    # Logo badge
    logo_size = 52
    c.setFillColor(colors.white)
    c.roundRect(margin + 20, height - margin - 20 - logo_size, logo_size, logo_size, 14, stroke=0, fill=1)
    c.setFillColor(header_color)
    c.setFont('Helvetica-Bold', 24)
    c.drawCentredString(margin + 20 + logo_size / 2, height - margin - 20 - logo_size / 2 + 2, 'RDV')

    # Header text
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 26)
    c.drawString(margin + 20 + logo_size + 16, height - margin - 42, 'Appointment Receipt')
    c.setFont('Helvetica', 10)
    c.drawString(margin + 20 + logo_size + 16, height - margin - 66, 'Official appointment confirmation from RDV Platform.')

    # Receipt metadata box
    meta_y = height - margin - 32
    c.setFont('Helvetica-Bold', 10)
    c.drawRightString(width - margin - 12, meta_y, f'Receipt No. {receipt_number}')
    c.setFont('Helvetica', 9)
    c.drawRightString(width - margin - 12, meta_y - 18, f'Generated on {generated_at}')

    # Status badge
    badge_width = 124
    badge_height = 28
    badge_x = width - margin - badge_width - 12
    badge_y = height - margin - header_height + 22
    c.setFillColor(status_color)
    c.roundRect(badge_x, badge_y, badge_width, badge_height, badge_height / 2, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 10)
    c.drawCentredString(badge_x + badge_width / 2, badge_y + 8, appointment_status.upper())

    # Section helper
    def draw_section(title, y_top):
        section_height = 110
        c.setFillColor(card_bg)
        c.roundRect(margin, y_top - section_height, width - 2 * margin, section_height, 14, stroke=0, fill=1)
        c.setFillColor(text_dark)
        c.setFont('Helvetica-Bold', 12)
        c.drawString(margin + 20, y_top - 26, title.upper())
        c.setStrokeColor(section_line)
        c.setLineWidth(0.8)
        c.line(margin + 20, y_top - 34, width - margin - 20, y_top - 34)
        return y_top - section_height

    content_top = height - margin - header_height - 22
    content_top = draw_section('Patient Information', content_top)
    c.setFont('Helvetica', 9)
    c.setFillColor(text_gray)
    c.drawString(margin + 20, content_top + 74, 'Full Name')
    c.setFillColor(text_dark)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(margin + 20, content_top + 58, user_name)
    c.setFillColor(text_gray)
    c.setFont('Helvetica', 9)
    c.drawString(margin + 20, content_top + 40, 'Email')
    c.setFillColor(text_dark)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(margin + 20, content_top + 24, user_email)

    content_top = draw_section('Appointment Information', content_top - 16)
    c.setFont('Helvetica', 9)
    c.setFillColor(text_gray)
    left_x = margin + 20
    right_x = width / 2 + 10
    c.drawString(left_x, content_top + 74, 'Appointment ID')
    c.setFillColor(text_dark)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(left_x, content_top + 58, str(appointment.id))
    c.setFillColor(text_gray)
    c.setFont('Helvetica', 9)
    c.drawString(left_x, content_top + 40, 'Appointment Type')
    c.setFillColor(text_dark)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(left_x, content_top + 24, appointment_type)
    c.setFillColor(text_gray)
    c.setFont('Helvetica', 9)
    c.drawString(right_x, content_top + 74, 'Date')
    c.setFillColor(text_dark)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(right_x, content_top + 58, appointment_date)
    c.setFillColor(text_gray)
    c.setFont('Helvetica', 9)
    c.drawString(right_x, content_top + 40, 'Time')
    c.setFillColor(text_dark)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(right_x, content_top + 24, appointment_time)

    content_top = draw_section('Confirmation Information', content_top - 16)
    c.setFont('Helvetica', 9)
    c.setFillColor(text_gray)
    c.drawString(margin + 20, content_top + 74, 'Confirmation Date')
    c.setFillColor(text_dark)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(margin + 20, content_top + 58, confirmation_date)
    c.setFillColor(text_gray)
    c.setFont('Helvetica', 9)
    c.drawString(margin + 20, content_top + 40, 'Administrator')
    c.setFillColor(text_dark)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(margin + 20, content_top + 24, admin_name)

    content_top = draw_section('Receipt Information', content_top - 16)
    c.setFont('Helvetica', 9)
    c.setFillColor(text_gray)
    c.drawString(margin + 20, content_top + 74, 'Receipt Number')
    c.setFillColor(text_dark)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(margin + 20, content_top + 58, receipt_number)
    c.setFillColor(text_gray)
    c.setFont('Helvetica', 9)
    c.drawString(margin + 20, content_top + 40, 'Generated On')
    c.setFillColor(text_dark)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(margin + 20, content_top + 24, generated_at)

    # QR code box
    qr_value = receipt_number
    qr_code = qr.QrCodeWidget(qr_value)
    qr_size = 68
    bounds = qr_code.getBounds()
    drawing = Drawing(qr_size, qr_size, transform=[qr_size / (bounds[2] - bounds[0]), 0, 0, qr_size / (bounds[3] - bounds[1]), 0, 0])
    drawing.add(qr_code)
    qr_x = width - margin - qr_size - 20
    qr_y = content_top + 20
    renderPDF.draw(drawing, c, qr_x, qr_y)
    c.setFont('Helvetica', 8)
    c.setFillColor(text_gray)
    c.drawRightString(qr_x + qr_size, qr_y - 8, 'Receipt QR code')

    # Footer
    footer_y = margin + 20
    c.setStrokeColor(section_line)
    c.setLineWidth(0.8)
    c.line(margin, footer_y + 46, width - margin, footer_y + 46)
    c.setFont('Helvetica-Bold', 10)
    c.setFillColor(text_dark)
    c.drawString(margin + 2, footer_y + 28, 'Thank you for using RDV Platform.')
    c.setFont('Helvetica', 8)
    c.setFillColor(text_gray)
    c.drawString(margin + 2, footer_y + 14, 'This receipt was generated automatically.')
    c.setFont('Helvetica-Oblique', 8)
    c.drawRightString(width - margin - 2, footer_y + 14, 'This document serves as proof of appointment confirmation.')

    c.save()
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@api.route("/health", methods=["GET"])
def api_health():
    return jsonify({"success": True, "message": "API health OK"}), 200


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
    )
    db.session.add(new_user)
    db.session.commit()

    # Connecte l'utilisateur directement après l'inscription pour éviter un second appel API
    session.clear()
    session["user_id"] = new_user.id
    log.info("[register] User %s created and logged in successfully.", new_user.email)

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


@api.route("/appointments/<int:appointment_id>/receipt", methods=["GET"])
def download_appointment_receipt(appointment_id):
    user = _resolve_user(request.args.get("user_id"))
    if not user:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    appointment = db.session.get(Appointment, appointment_id)
    if not appointment:
        return jsonify({"success": False, "message": "Rendez-vous introuvable."}), 404

    if user.role != "admin" and appointment.user_id != user.id:
        return jsonify({"success": False, "message": "Accès non autorisé."}), 403

    if appointment.status != "Confirmé":
        return jsonify({"success": False, "message": "Le reçu n'est disponible que pour les rendez-vous confirmés."}), 400

    admin = User.query.filter_by(role="admin").first()
    admin_name = admin.fullname if admin else "Administrateur"

    try:
        pdf_buffer = _generate_appointment_receipt_pdf(appointment, admin_name)
        response = make_response(pdf_buffer.getvalue())
        response.headers.set('Content-Type', 'application/pdf')
        response.headers.set('Content-Disposition', f'attachment; filename=receipt-{appointment_id}.pdf')
        return response
    except Exception as e:
        log.exception("Error generating receipt PDF for appointment %s", appointment_id)
        return jsonify({"success": False, "message": "Erreur lors de la génération du reçu."}), 500


@api.route("/appointments", methods=["GET"])
def get_current_user_appointments():
    """Rendez-vous de l'utilisateur connecté (session ou ?user_id=)."""
    user_id_param = request.args.get("user_id")
    user = _resolve_user(user_id_param)
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
    log.info("[admin/appointments] %d rendez-vous trouvés", len(appointments))
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

        log.info("[dashboard/stats] appointments=%s users=%s recent_count=%s",
                 int(counts.appointments or 0), User.query.count(), len(recent))

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

    # OPTIMISATION (N+1) : Utilise subqueryload pour les messages et joinedload pour le sender de chaque message.
    # Cela évite une requête par message pour récupérer le nom de l'expéditeur.
    conversations = Conversation.query.options(
        subqueryload(Conversation.messages).options(
            joinedload(Message.sender)
        )
    ).filter_by(user_id=user_id).order_by(Conversation.created_at.desc()).all()

    return jsonify({"success": True, "data": [serialize_conversation(c) for c in conversations]}), 200


@api.route("/messages/admin", methods=["GET"])
def get_admin_messages():
    # OPTIMISATION (N+1) : Charge en amont l'utilisateur de la conversation et les messages avec leurs expéditeurs.
    conversations = Conversation.query.options(
        joinedload(Conversation.user),
        subqueryload(Conversation.messages).joinedload(Message.sender)
    ).order_by(Conversation.created_at.desc()).all()
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


@api.route("/messages/<int:message_id>", methods=["DELETE"])
@admin_required
def delete_message(message_id):
    """Supprime un message spécifique. Accessible uniquement par les administrateurs."""
    log.info("[DELETE /messages/%d] Tentative de suppression par l'admin.", message_id)

    message = db.session.get(Message, message_id)
    if not message:
        log.warning("[DELETE /messages/%d] Message introuvable.", message_id)
        return jsonify({"success": False, "message": "Message introuvable."}), 404

    try:
        db.session.delete(message)
        db.session.commit()
        log.info("[DELETE /messages/%d] Message supprimé avec succès.", message_id)
        return jsonify({"success": True, "message": "Message supprimé avec succès."}), 200
    except Exception as e:
        db.session.rollback()
        log.error("[DELETE /messages/%d] Erreur serveur lors de la suppression : %s", message_id, e)
        return jsonify({"success": False, "message": "Erreur interne du serveur lors de la suppression."}), 500


@api.route("/messages/conversation/<int:conversation_id>", methods=["DELETE"])
@admin_required
def delete_conversation(conversation_id):
    """Supprime une conversation et tous ses messages. Accessible uniquement par les administrateurs."""
    log.info("[DELETE /messages/conversation/%d] Tentative de suppression par l'admin.", conversation_id)

    conversation = db.session.get(Conversation, conversation_id)
    if not conversation:
        log.warning("[DELETE /messages/conversation/%d] Conversation introuvable.", conversation_id)
        return jsonify({"success": False, "message": "Conversation introuvable."}), 404

    try:
        db.session.delete(conversation)
        db.session.commit()
        log.info("[DELETE /messages/conversation/%d] Conversation supprimée avec succès.", conversation_id)
        return jsonify({"success": True, "message": "Conversation supprimée avec succès."}), 200
    except Exception as e:
        db.session.rollback()
        log.error("[DELETE /messages/conversation/%d] Erreur serveur lors de la suppression : %s", conversation_id, e)
        return jsonify({"success": False, "message": "Erreur interne du serveur lors de la suppression."}), 500
