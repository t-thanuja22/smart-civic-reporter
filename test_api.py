import io
from conftest import login


def test_register_new_user_success(client):
    resp = client.post("/register", data={
        "name": "Alice", "email": "alice@test.com", "phone": "9999999999",
        "password": "Secret123"
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_register_duplicate_email_rejected(client):
    client.post("/register", data={"name": "Bob", "email": "bob@test.com", "password": "Secret123"})
    resp = client.post("/register", data={"name": "Bob2", "email": "bob@test.com",
                                           "password": "Secret123"}, follow_redirects=True)
    assert b"already exists" in resp.data


def test_login_wrong_password_rejected(client):
    client.post("/register", data={"name": "Carl", "email": "carl@test.com", "password": "Secret123"})
    resp = login(client, "carl@test.com", "WrongPassword")
    assert b"Invalid email or password" in resp.data


def test_submit_complaint_without_location_rejected(client):
    client.post("/register", data={"name": "Frank", "email": "frank@test.com", "password": "Secret123"})
    login(client, "frank@test.com", "Secret123")
    resp = client.post("/submit", data={"description": "Pothole on main road"},
                        follow_redirects=True)
    assert b"Location not captured" in resp.data


def test_submit_valid_complaint_success(client):
    client.post("/register", data={"name": "Hana", "email": "hana@test.com", "password": "Secret123"})
    login(client, "hana@test.com", "Secret123")
    data = {
        "description": "Street light not working near park",
        "latitude": "13.0800", "longitude": "80.2700", "address_text": "Near City Park",
    }
    resp = client.post("/submit", data=data, follow_redirects=True)
    assert resp.status_code == 200


def test_dropdown_category_overrides_nlp_guess(client):
    client.post("/register", data={"name": "Leo", "email": "leo@test.com", "password": "Secret123"})
    login(client, "leo@test.com", "Secret123")
    resp = client.post("/submit", data={
        "description": "pothole shaped puddle near the gate",
        "latitude": "13.0800", "longitude": "80.2700",
        "category": "Water Leakage",
    }, follow_redirects=True)
    assert b"Municipal Water Board" in resp.data


def test_voice_note_upload_accepted(client):
    client.post("/register", data={"name": "Maya", "email": "maya@test.com", "password": "Secret123"})
    login(client, "maya@test.com", "Secret123")
    data = {
        "description": "Pothole near the school gate, recorded a voice note instead",
        "latitude": "13.0800", "longitude": "80.2700",
        "voice_note": (io.BytesIO(b"fake audio bytes"), "note.webm"),
    }
    resp = client.post("/submit", data=data, content_type="multipart/form-data",
                        follow_redirects=True)
    assert resp.status_code == 200


def test_admin_dashboard_blocked_for_citizen(client):
    client.post("/register", data={"name": "Eve", "email": "eve@test.com", "password": "Secret123"})
    login(client, "eve@test.com", "Secret123")
    resp = client.get("/admin", follow_redirects=True)
    assert b"Admin access only" in resp.data


def test_citizen_login_rejects_worker_credentials(client, app):
    from models import db, User
    with app.app_context():
        worker = User(name="Test Worker", email="worker@test.com", role="worker",
                      department="Electricity Board (EB)")
        worker.set_password("Secret123")
        db.session.add(worker)
        db.session.commit()

    resp = client.post("/login", data={"email": "worker@test.com", "password": "Secret123"},
                        follow_redirects=True)
    assert b"Please use the worker or admin login page" in resp.data


def test_worker_login_rejects_citizen_credentials(client):
    client.post("/register", data={"name": "Fay", "email": "fay@test.com", "password": "Secret123"})
    resp = client.post("/worker/login", data={"email": "fay@test.com", "password": "Secret123"},
                        follow_redirects=True)
    assert b"This login is for department workers only" in resp.data


def test_worker_sees_only_own_department_complaints(client, app):
    from models import db, User

    client.post("/register", data={"name": "Gus", "email": "gus@test.com", "password": "Secret123"})
    login(client, "gus@test.com", "Secret123")
    client.post("/submit", data={"description": "big pothole on main road",
                                  "latitude": "13.08", "longitude": "80.27"}, follow_redirects=True)
    client.get("/logout")

    with app.app_context():
        eb_worker = User(name="EB Worker", email="ebworker@test.com", role="worker",
                         department="Electricity Board (EB)")
        eb_worker.set_password("Secret123")
        db.session.add(eb_worker)
        db.session.commit()

    login(client, "ebworker@test.com", "Secret123")
    resp = client.get("/worker")
    assert resp.status_code == 200
    assert b"pothole" not in resp.data.lower()


# ---------- new features: analytics, feedback, notifications, public map ----------

def test_analytics_blocked_for_citizen(client):
    client.post("/register", data={"name": "Ivy", "email": "ivy@test.com", "password": "Secret123"})
    login(client, "ivy@test.com", "Secret123")
    resp = client.get("/admin/analytics", follow_redirects=True)
    assert b"Admin access only" in resp.data


def test_analytics_accessible_to_admin(client, app):
    from models import db, User
    with app.app_context():
        admin = User(name="Admin", email="admin2@test.com", role="admin")
        admin.set_password("Secret123")
        db.session.add(admin)
        db.session.commit()
    client.post("/admin/login", data={"email": "admin2@test.com", "password": "Secret123"})
    resp = client.get("/admin/analytics")
    assert resp.status_code == 200


def test_feedback_rejected_before_completed(client):
    client.post("/register", data={"name": "Jon", "email": "jon2@test.com", "password": "Secret123"})
    login(client, "jon2@test.com", "Secret123")
    client.post("/submit", data={"description": "pothole on ring road",
                                  "latitude": "13.08", "longitude": "80.27"}, follow_redirects=True)
    resp = client.get("/my-complaints")
    # complaint starts at "Pending Approval", not Completed -- feedback form shouldn't be postable yet
    from models import Complaint
    complaint = Complaint.query.first()
    fb_resp = client.post(f"/complaint/{complaint.id}/feedback",
                           data={"rating": "5"}, follow_redirects=True)
    assert b"once it's marked Completed" in fb_resp.data


def test_notifications_created_on_status_update(client, app):
    from models import db, User, Complaint, Notification

    client.post("/register", data={"name": "Kim", "email": "kim2@test.com", "password": "Secret123"})
    login(client, "kim2@test.com", "Secret123")
    client.post("/submit", data={"description": "street light not working",
                                  "latitude": "13.08", "longitude": "80.27"}, follow_redirects=True)
    client.get("/logout")

    with app.app_context():
        admin = User(name="Admin", email="admin3@test.com", role="admin")
        admin.set_password("Secret123")
        db.session.add(admin)
        db.session.commit()
        complaint = Complaint.query.first()
        complaint_id = complaint.id

    client.post("/admin/login", data={"email": "admin3@test.com", "password": "Secret123"})
    client.post(f"/admin/complaint/{complaint_id}/update",
                data={"status": "Approved", "remarks": "checked"}, follow_redirects=True)

    with app.app_context():
        assert Notification.query.count() == 1


def test_public_map_loads_without_login(client):
    resp = client.get("/map")
    assert resp.status_code == 200


def test_notifications_page_requires_citizen_role(client, app):
    from models import db, User
    with app.app_context():
        admin = User(name="Admin", email="admin4@test.com", role="admin")
        admin.set_password("Secret123")
        db.session.add(admin)
        db.session.commit()
    client.post("/admin/login", data={"email": "admin4@test.com", "password": "Secret123"})
    resp = client.get("/notifications", follow_redirects=True)
    assert b"Notifications are for citizens" in resp.data


def test_green_points_awarded_for_new_complaint(client, app):
    from models import User

    client.post("/register", data={"name": "Nina", "email": "nina@test.com", "password": "Secret123"})
    login(client, "nina@test.com", "Secret123")
    client.post("/submit", data={"description": "pothole near my street",
                                  "latitude": "13.08", "longitude": "80.27"}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="nina@test.com").first()
        assert user.green_points == 10


def test_green_points_awarded_for_feedback(client, app):
    from models import db, User, Complaint

    client.post("/register", data={"name": "Omar", "email": "omar@test.com", "password": "Secret123"})
    login(client, "omar@test.com", "Secret123")
    client.post("/submit", data={"description": "pothole near my street",
                                  "latitude": "13.08", "longitude": "80.27"}, follow_redirects=True)

    with app.app_context():
        complaint = Complaint.query.first()
        complaint.status = "Completed"
        db.session.commit()
        complaint_id = complaint.id

    client.post(f"/complaint/{complaint_id}/feedback", data={"rating": "5"}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="omar@test.com").first()
        assert user.green_points == 15  # 10 for filing + 5 for feedback


def test_my_points_page_requires_citizen(client, app):
    from models import db, User
    with app.app_context():
        admin = User(name="Admin", email="admin5@test.com", role="admin")
        admin.set_password("Secret123")
        db.session.add(admin)
        db.session.commit()
    client.post("/admin/login", data={"email": "admin5@test.com", "password": "Secret123"})
    resp = client.get("/my-points", follow_redirects=True)
    assert b"Green Points are for citizens" in resp.data


def test_admin_can_see_registered_citizens(client, app):
    from models import db, User
    client.post("/register", data={"name": "Priti", "email": "priti@test.com", "password": "Secret123"})
    with app.app_context():
        admin = User(name="Admin", email="admin6@test.com", role="admin")
        admin.set_password("Secret123")
        db.session.add(admin)
        db.session.commit()
    client.post("/admin/login", data={"email": "admin6@test.com", "password": "Secret123"})
    resp = client.get("/admin/workers")
    assert b"Priti" in resp.data


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_api_complaints_returns_json_list(client):
    resp = client.get("/api/complaints")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)
