"""
Database models for Smart Civic Reporter.
Uses Flask-SQLAlchemy (SQLite by default -- swap the URI for MySQL/Postgres in production).
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="citizen")  # citizen | admin | worker
    department = db.Column(db.String(50))  # only used when role == 'worker'
    green_points = db.Column(db.Integer, default=0)  # citizen engagement score
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    complaints = db.relationship("Complaint", backref="reporter", lazy=True)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)
    complaint_code = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    description = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(255))
    voice_note_path = db.Column(db.String(255))

    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    address_text = db.Column(db.String(255))

    category = db.Column(db.String(50))
    department = db.Column(db.String(50))
    priority = db.Column(db.String(20))
    status = db.Column(db.String(30), default="Pending Approval")

    duplicate_of = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=True)
    report_count = db.Column(db.Integer, default=1)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    logs = db.relationship("ComplaintStatusLog", backref="complaint", lazy=True,
                            order_by="ComplaintStatusLog.changed_at")
    feedback = db.relationship("Feedback", backref="complaint", uselist=False, lazy=True)


class ComplaintStatusLog(db.Model):
    __tablename__ = "complaint_status_logs"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False)
    status = db.Column(db.String(30), nullable=False)
    remarks = db.Column(db.String(255))
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)


class Feedback(db.Model):
    """Citizen rating left after a complaint is marked Completed."""
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), unique=True, nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    """In-app stand-in for an email/SMS alert sent to a citizen when their
    complaint's status changes. (Wiring this to a real email/SMS gateway --
    e.g. SendGrid/Twilio -- is a drop-in swap: just call the gateway API
    wherever a Notification row is created below.)"""
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class GreenPointsLog(db.Model):
    """Audit trail of green points earned by citizens for civic participation --
    reporting new issues, confirming existing ones (duplicate merges), and
    leaving feedback. Sum this table per user for their running total."""
    __tablename__ = "green_points_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
