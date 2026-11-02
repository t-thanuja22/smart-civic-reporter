"""
Smart Civic Reporter -- main Flask application.
Run with:  python app.py
Then open http://127.0.0.1:5000
"""
import os
import uuid
from datetime import datetime
from collections import Counter

from flask import (Flask, render_template, request, redirect, url_for, flash, jsonify, session,
                   send_from_directory)
from flask_login import (LoginManager, login_user, logout_user, login_required,
                          current_user)
from werkzeug.utils import secure_filename

from models import db, User, Complaint, ComplaintStatusLog, Feedback, Notification, GreenPointsLog
from categorizer import classify_department, classify_priority, find_duplicate, \
    department_for_category, DROPDOWN_CATEGORIES, DEPARTMENTS
from translations import translate
import storage

SUPPORTED_LANGUAGES = {"en": "English", "ta": "தமிழ்", "hi": "हिंदी"}

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Old (pre-fix) in-project locations -- only used to COPY existing data into the permanent folder.
LEGACY_DB = os.path.join(BASE_DIR, "civic.db")
LEGACY_UPLOADS = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_AUDIO_EXTENSIONS = {"webm", "mp3", "wav", "ogg", "m4a", "aac"}

STATUS_STAGES = ["Pending Approval", "Approved", "Under Process", "Completed", "Rejected"]

# Green Points -- rewards citizen civic engagement
POINTS_NEW_COMPLAINT = 10   # filing a fresh, original complaint
POINTS_MONITORING = 3       # confirming/reporting an issue someone else already flagged
POINTS_FEEDBACK = 5         # rating a resolved complaint


def create_app(testing: bool = False, data_dir=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "change-this-secret-key-in-production"

    if testing and data_dir is None:
        # unit tests: throw-away in-memory DB and a temp uploads folder (never the real data)
        import tempfile
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["UPLOAD_FOLDER"] = tempfile.mkdtemp(prefix="civic_test_uploads_")
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
    else:
        # PERMANENT storage: one fixed folder, independent of where the project is extracted.
        data = storage.get_data_dir(data_dir)
        for msg in storage.migrate_legacy_data(data, LEGACY_DB, LEGACY_UPLOADS):
            print("[storage]", msg)
        try:
            backup = storage.backup_db(data)
            if backup:
                print("[storage] Backup written:", backup)
        except Exception as exc:  # a failed backup must never stop the app
            print("[storage] Backup skipped:", exc)
        app.config["DATA_DIR"] = str(data)
        app.config["UPLOAD_FOLDER"] = str(data / "uploads")
        app.config["SQLALCHEMY_DATABASE_URI"] = storage.sqlite_uri(data / storage.DB_FILENAME)
        print("[storage] Database :", data / storage.DB_FILENAME)
        print("[storage] Uploads  :", data / "uploads")
        if testing:
            app.config["TESTING"] = True

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    def allowed_file(filename):
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

    def allowed_audio_file(filename):
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS

    def next_status(current):
        order = ["Pending Approval", "Approved", "Under Process", "Completed"]
        if current == "Rejected" or current not in order:
            return []
        idx = order.index(current)
        options = order[idx + 1:]
        if current != "Rejected":
            options = options + ["Rejected"]
        return options

    def award_points(user_id, points, reason):
        """Log the award for a real history/audit trail AND keep the cached
        User.green_points total in sync (used for fast lookups/leaderboards)."""
        db.session.add(GreenPointsLog(user_id=user_id, points=points, reason=reason))
        user = User.query.get(user_id)
        if user:
            user.green_points = (user.green_points or 0) + points

    @app.context_processor
    def inject_unread_notifications():
        if current_user.is_authenticated and current_user.role == "citizen":
            count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
            return {"unread_notifications": count, "my_green_points": current_user.green_points or 0}
        return {"unread_notifications": 0, "my_green_points": 0}

    @app.context_processor
    def inject_language():
        return {
            "current_lang": session.get("lang", "en"),
            "supported_languages": SUPPORTED_LANGUAGES,
        }

    app.jinja_env.globals["t"] = lambda key: translate(key, session.get("lang", "en"))

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        """Serve complaint photos / voice notes from the permanent uploads folder."""
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.route("/lang/<lang_code>")
    def set_language(lang_code):
        if lang_code in SUPPORTED_LANGUAGES:
            session["lang"] = lang_code
        return redirect(request.referrer or url_for("index"))

    # ---------------------------------------------------------------- routes
    @app.route("/")
    def index():
        total = Complaint.query.count()
        resolved = Complaint.query.filter_by(status="Completed").count()
        pending = total - resolved
        recent = Complaint.query.order_by(Complaint.created_at.desc()).limit(6).all()
        return render_template("index.html", total=total, resolved=resolved,
                                pending=pending, recent=recent)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip()
            password = request.form.get("password", "")

            if not name or not email or not password:
                flash("Name, email and password are required.", "error")
                return render_template("register.html")

            if User.query.filter_by(email=email).first():
                flash("An account with this email already exists.", "error")
                return render_template("register.html")

            user = User(name=name, email=email, phone=phone, role="citizen")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):
                if user.role != "citizen":
                    flash("This login is for citizens. Please use the worker or admin login page.", "error")
                    return render_template("login.html")
                login_user(user)
                flash(f"Welcome back, {user.name}.", "success")
                return redirect(url_for("my_complaints"))

            flash("Invalid email or password.", "error")
        return render_template("login.html")

    @app.route("/worker/login", methods=["GET", "POST"])
    def worker_login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):
                if user.role != "worker":
                    flash("This login is for department workers only.", "error")
                    return render_template("worker_login.html")
                login_user(user)
                flash(f"Welcome back, {user.name}.", "success")
                return redirect(url_for("worker_dashboard"))

            flash("Invalid email or password.", "error")
        return render_template("worker_login.html")

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):
                if user.role != "admin":
                    flash("This login is for administrators only.", "error")
                    return render_template("admin_login.html")
                login_user(user)
                flash(f"Welcome back, {user.name}.", "success")
                return redirect(url_for("admin_dashboard"))

            flash("Invalid email or password.", "error")
        return render_template("admin_login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    @app.route("/submit", methods=["GET", "POST"])
    @login_required
    def submit_complaint():
        if request.method == "POST":
            description = request.form.get("description", "").strip()
            latitude = request.form.get("latitude")
            longitude = request.form.get("longitude")
            address_text = request.form.get("address_text", "")

            if not description:
                flash("Please describe the issue.", "error")
                return render_template("submit.html", dropdown_categories=DROPDOWN_CATEGORIES)
            if not latitude or not longitude:
                flash("Location not captured. Please allow GPS access and try again.", "error")
                return render_template("submit.html", dropdown_categories=DROPDOWN_CATEGORIES)

            latitude, longitude = float(latitude), float(longitude)

            image_path = None
            file = request.files.get("image")
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit(".", 1)[1].lower()
                filename = secure_filename(f"{uuid.uuid4().hex}.{ext}")
                os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                image_path = filename

            voice_note_path = None
            voice_file = request.files.get("voice_note")
            if voice_file and voice_file.filename and allowed_audio_file(voice_file.filename):
                ext = voice_file.filename.rsplit(".", 1)[1].lower()
                voice_filename = secure_filename(f"{uuid.uuid4().hex}.{ext}")
                os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                voice_file.save(os.path.join(app.config["UPLOAD_FOLDER"], voice_filename))
                voice_note_path = voice_filename

            selected_category = request.form.get("category", "").strip()
            if selected_category and selected_category != "Other":
                category = selected_category
                department = department_for_category(category)
            else:
                category, department = classify_department(description)

            candidates = Complaint.query.filter_by(category=category).all()
            dup = find_duplicate(latitude, longitude, category, candidates)

            if dup:
                dup.report_count = (dup.report_count or 1) + 1
                dup.priority = classify_priority(description, dup.report_count)
                db.session.add(ComplaintStatusLog(
                    complaint_id=dup.id, status=dup.status,
                    remarks=f"Additional citizen report merged (total reports: {dup.report_count})"))
                award_points(current_user.id, POINTS_MONITORING, f"Confirmed existing issue {dup.complaint_code}")
                db.session.commit()
                flash("A report for this issue already exists nearby -- your report has been "
                      f"merged with complaint {dup.complaint_code} and its priority updated. "
                      f"+{POINTS_MONITORING} Green Points for monitoring this issue!", "info")
                return redirect(url_for("complaint_detail", complaint_id=dup.id))

            priority = classify_priority(description, report_count=1)
            code = "SCR-" + uuid.uuid4().hex[:8].upper()

            complaint = Complaint(
                complaint_code=code, user_id=current_user.id, description=description,
                image_path=image_path, voice_note_path=voice_note_path,
                latitude=latitude, longitude=longitude,
                address_text=address_text, category=category, department=department,
                priority=priority, status="Pending Approval",
            )
            db.session.add(complaint)
            award_points(current_user.id, POINTS_NEW_COMPLAINT, f"Filed complaint {code}")
            db.session.commit()

            db.session.add(ComplaintStatusLog(complaint_id=complaint.id,
                                               status="Pending Approval",
                                               remarks="Complaint auto-created by citizen report"))
            db.session.commit()

            flash(f"Complaint {code} submitted and routed to {department}. "
                  f"+{POINTS_NEW_COMPLAINT} Green Points earned!", "success")
            return redirect(url_for("complaint_detail", complaint_id=complaint.id))

        return render_template("submit.html", dropdown_categories=DROPDOWN_CATEGORIES)

    @app.route("/my-complaints")
    @login_required
    def my_complaints():
        complaints = Complaint.query.filter_by(user_id=current_user.id) \
            .order_by(Complaint.created_at.desc()).all()
        return render_template("status.html", complaints=complaints)

    @app.route("/complaint/<int:complaint_id>")
    @login_required
    def complaint_detail(complaint_id):
        complaint = Complaint.query.get_or_404(complaint_id)
        if current_user.role == "citizen" and complaint.user_id != current_user.id:
            flash("You can only view your own complaints.", "error")
            return redirect(url_for("my_complaints"))
        if current_user.role == "worker" and complaint.department != current_user.department:
            flash("This complaint isn't assigned to your department.", "error")
            return redirect(url_for("worker_dashboard"))
        return render_template("complaint_detail.html", c=complaint,
                                next_statuses=next_status(complaint.status))

    @app.route("/complaint/<int:complaint_id>/feedback", methods=["POST"])
    @login_required
    def submit_feedback(complaint_id):
        complaint = Complaint.query.get_or_404(complaint_id)
        if complaint.user_id != current_user.id:
            flash("You can only rate your own complaints.", "error")
            return redirect(url_for("my_complaints"))
        if complaint.status != "Completed":
            flash("You can only rate a complaint once it's marked Completed.", "error")
            return redirect(url_for("complaint_detail", complaint_id=complaint.id))
        if complaint.feedback:
            flash("You've already rated this complaint.", "error")
            return redirect(url_for("complaint_detail", complaint_id=complaint.id))

        rating = request.form.get("rating", type=int)
        comment = request.form.get("comment", "").strip()
        if not rating or rating < 1 or rating > 5:
            flash("Please choose a rating between 1 and 5.", "error")
            return redirect(url_for("complaint_detail", complaint_id=complaint.id))

        db.session.add(Feedback(complaint_id=complaint.id, rating=rating, comment=comment))
        award_points(current_user.id, POINTS_FEEDBACK, f"Rated resolved complaint {complaint.complaint_code}")
        db.session.commit()
        flash(f"Thanks for the feedback! +{POINTS_FEEDBACK} Green Points earned.", "success")
        return redirect(url_for("complaint_detail", complaint_id=complaint.id))

    @app.route("/admin")
    @login_required
    def admin_dashboard():
        if current_user.role != "admin":
            flash("Admin access only.", "error")
            return redirect(url_for("index"))

        status_filter = request.args.get("status")
        dept_filter = request.args.get("department")

        query = Complaint.query
        if status_filter:
            query = query.filter_by(status=status_filter)
        if dept_filter:
            query = query.filter_by(department=dept_filter)

        complaints = query.order_by(Complaint.priority.desc(), Complaint.created_at.desc()).all()
        departments = [d[0] for d in db.session.query(Complaint.department).distinct()]
        return render_template("admin.html", complaints=complaints, departments=departments,
                                statuses=STATUS_STAGES)

    @app.route("/admin/analytics")
    @login_required
    def admin_analytics():
        if current_user.role != "admin":
            flash("Admin access only.", "error")
            return redirect(url_for("index"))

        complaints = Complaint.query.all()
        by_department = Counter(c.department for c in complaints)
        by_category = Counter(c.category for c in complaints)
        by_status = Counter(c.status for c in complaints)
        by_priority = Counter(c.priority for c in complaints)

        ratings = [f.rating for f in Feedback.query.all()]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

        return render_template("admin_analytics.html",
                                by_department=by_department, by_category=by_category,
                                by_status=by_status, by_priority=by_priority,
                                avg_rating=avg_rating, rating_count=len(ratings),
                                total=len(complaints))

    @app.route("/admin/workers", methods=["GET", "POST"])
    @login_required
    def manage_workers():
        if current_user.role != "admin":
            flash("Admin access only.", "error")
            return redirect(url_for("index"))

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            department = request.form.get("department", "")

            if not name or not email or not password or not department:
                flash("All fields are required to create a worker account.", "error")
            elif User.query.filter_by(email=email).first():
                flash("An account with this email already exists.", "error")
            else:
                worker = User(name=name, email=email, role="worker", department=department)
                worker.set_password(password)
                db.session.add(worker)
                db.session.commit()
                flash(f"Worker account created for {name} ({department}).", "success")
            return redirect(url_for("manage_workers"))

        workers = User.query.filter_by(role="worker").order_by(User.department).all()
        citizens = User.query.filter_by(role="citizen").order_by(User.green_points.desc()).all()
        return render_template("manage_workers.html", workers=workers, departments=DEPARTMENTS,
                                citizens=citizens)

    @app.route("/worker")
    @login_required
    def worker_dashboard():
        if current_user.role != "worker":
            flash("Worker access only.", "error")
            return redirect(url_for("index"))

        status_filter = request.args.get("status")
        query = Complaint.query.filter_by(department=current_user.department)
        if status_filter:
            query = query.filter_by(status=status_filter)

        complaints = query.order_by(Complaint.priority.desc(), Complaint.created_at.desc()).all()
        return render_template("worker_dashboard.html", complaints=complaints, statuses=STATUS_STAGES)

    @app.route("/admin/complaint/<int:complaint_id>/update", methods=["POST"])
    @login_required
    def update_status(complaint_id):
        if current_user.role not in ("admin", "worker"):
            flash("Access denied.", "error")
            return redirect(url_for("index"))

        complaint = Complaint.query.get_or_404(complaint_id)

        if current_user.role == "worker" and complaint.department != current_user.department:
            flash("This complaint isn't assigned to your department.", "error")
            return redirect(url_for("worker_dashboard"))

        new_status = request.form.get("status")
        remarks = request.form.get("remarks", "")

        if new_status not in next_status(complaint.status) and new_status != complaint.status:
            flash("Invalid status transition.", "error")
            return redirect(url_for("admin_dashboard" if current_user.role == "admin" else "worker_dashboard"))

        complaint.status = new_status
        complaint.updated_at = datetime.utcnow()
        db.session.add(ComplaintStatusLog(complaint_id=complaint.id, status=new_status,
                                           remarks=f"Updated by {current_user.name} ({current_user.role}). {remarks}".strip()))

        # simulated email/SMS notification to the citizen who filed it
        db.session.add(Notification(
            user_id=complaint.user_id, complaint_id=complaint.id,
            message=f"Your complaint {complaint.complaint_code} ({complaint.category}) is now '{new_status}'."
        ))
        db.session.commit()
        flash(f"Complaint {complaint.complaint_code} marked as {new_status}.", "success")
        return redirect(url_for("admin_dashboard" if current_user.role == "admin" else "worker_dashboard"))

    @app.route("/notifications")
    @login_required
    def notifications():
        if current_user.role != "citizen":
            flash("Notifications are for citizens.", "error")
            return redirect(url_for("index"))

        items = Notification.query.filter_by(user_id=current_user.id) \
            .order_by(Notification.created_at.desc()).all()
        for n in items:
            n.is_read = True
        db.session.commit()
        return render_template("notifications.html", notifications=items)

    @app.route("/my-points")
    @login_required
    def my_points():
        if current_user.role != "citizen":
            flash("Green Points are for citizens.", "error")
            return redirect(url_for("index"))

        history = GreenPointsLog.query.filter_by(user_id=current_user.id) \
            .order_by(GreenPointsLog.created_at.desc()).all()
        return render_template("my_points.html", history=history,
                                total=current_user.green_points or 0)

    @app.route("/map")
    def public_map():
        return render_template("public_map.html")

    # ---------------------------------------------------------- JSON API
    @app.route("/api/complaints")
    def api_complaints():
        complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
        return jsonify([{
            "id": c.id, "code": c.complaint_code, "category": c.category,
            "department": c.department, "priority": c.priority, "status": c.status,
            "latitude": c.latitude, "longitude": c.longitude,
            "created_at": c.created_at.isoformat(),
        } for c in complaints])

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


def seed_defaults(app):
    """Create the default admin + one demo worker per department, if they don't exist yet.
    Called both by the local dev server (__main__ below) and by wsgi.py for deployment."""
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(role="admin").first():
            admin = User(name="City Admin", email="admin@civic.gov", role="admin")
            admin.set_password("Admin@123")
            db.session.add(admin)
            db.session.commit()
            print("Seeded default admin -> email: admin@civic.gov  password: Admin@123")

        dept_seed_emails = {
            "Electricity Board (EB)": ("Ravi (EB Lineman)", "worker.eb@civic.gov"),
            "Municipal Water Board": ("Suresh (Water Board)", "worker.water@civic.gov"),
            "Public Works Department (PWD)": ("Kumar (PWD Engineer)", "worker.pwd@civic.gov"),
            "Municipal Corporation - Sanitation": ("Anitha (Sanitation)", "worker.sanitation@civic.gov"),
            "Municipal Corporation - General": ("Priya (Corporation)", "worker.corp@civic.gov"),
            "Public Health Department": ("Dinesh (Public Health)", "worker.health@civic.gov"),
            "Animal Control Department": ("Muthu (Animal Control)", "worker.animal@civic.gov"),
        }
        if not User.query.filter_by(role="worker").first():
            for department, (name, email) in dept_seed_emails.items():
                worker = User(name=name, email=email, role="worker", department=department)
                worker.set_password("Worker@123")
                db.session.add(worker)
            db.session.commit()
            print("Seeded demo workers (password for all: Worker@123):")
            for department, (name, email) in dept_seed_emails.items():
                print(f"  {email}  -> {department}")


if __name__ == "__main__":
    app = create_app()
    seed_defaults(app)
    app.run(debug=True, host="0.0.0.0", port=5000)
