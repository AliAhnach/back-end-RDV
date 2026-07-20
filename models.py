from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    # Relation : un utilisateur possède plusieurs rendez-vous
    appointments = db.relationship(
        "Appointment",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )


class Appointment(db.Model):
    __tablename__ = "appointment"

    id = db.Column(db.Integer, primary_key=True)

    service = db.Column(db.String(100), nullable=False)

    appointment_date = db.Column(db.Date, nullable=False)

    appointment_time = db.Column(db.Time, nullable=False)

    description = db.Column(db.Text)

    status = db.Column(
        db.String(20),
        default="En attente",
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )