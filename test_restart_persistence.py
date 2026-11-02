"""
Full-application restart test: create accounts + complaints, 'stop' the app,
start a brand-new app instance on the SAME data folder, and check nothing was lost.
Run: python -m pytest tests/test_restart_persistence.py -v
"""
import io
from app import create_app, seed_defaults
from models import db, User, Complaint, Feedback, Notification, ComplaintStatusLog


def start(data_dir):
    app = create_app(testing=True, data_dir=str(data_dir))   # permanent-storage mode, temp folder
    seed_defaults(app)
    return app


def stop(app):
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def post_login(client, url, email, pw):
    return client.post(url, data={"email": email, "password": pw}, follow_redirects=True)


def test_all_data_survives_a_restart(tmp_path):
    # ---------- first run ----------
    app = start(tmp_path)
    c = app.test_client()
    c.post("/register", data={"name": "Asha", "email": "asha@test.com", "password": "Secret123"})
    post_login(c, "/login", "asha@test.com", "Secret123")
    for i, desc in enumerate(["big pothole on main road", "street light not working", "garbage not cleaned"]):
        c.post("/submit", data={"description": desc, "latitude": str(13.0 + i), "longitude": "80.27",
                                "image": (io.BytesIO(b"fake-jpg"), "a.jpg")},
               content_type="multipart/form-data", follow_redirects=True)
    c.get("/logout")

    post_login(c, "/admin/login", "admin@civic.gov", "Admin@123")
    with app.app_context():
        first = Complaint.query.order_by(Complaint.id).first()
        cid, code, image = first.id, first.complaint_code, first.image_path
    c.post(f"/admin/complaint/{cid}/update", data={"status": "Approved", "remarks": "ok"})
    c.post(f"/admin/complaint/{cid}/update", data={"status": "Under Process", "remarks": ""})
    c.post(f"/admin/complaint/{cid}/update", data={"status": "Completed", "remarks": "fixed"})
    c.get("/logout")
    post_login(c, "/login", "asha@test.com", "Secret123")
    c.post(f"/complaint/{cid}/feedback", data={"rating": "4", "comment": "good"}, follow_redirects=True)

    with app.app_context():
        before = dict(users=User.query.count(), complaints=Complaint.query.count(),
                      logs=ComplaintStatusLog.query.count(), feedback=Feedback.query.count(),
                      notes=Notification.query.count(),
                      points=User.query.filter_by(email="asha@test.com").first().green_points)
    assert before["complaints"] == 3 and before["feedback"] == 1
    stop(app)                                   # <-- server stopped

    # ---------- second run (fresh process, same folder) ----------
    app2 = start(tmp_path)
    c2 = app2.test_client()
    with app2.app_context():
        after = dict(users=User.query.count(), complaints=Complaint.query.count(),
                     logs=ComplaintStatusLog.query.count(), feedback=Feedback.query.count(),
                     notes=Notification.query.count(),
                     points=User.query.filter_by(email="asha@test.com").first().green_points)
        assert Complaint.query.get(cid).status == "Completed"
        assert Complaint.query.get(cid).image_path == image
    assert after == before                      # nothing reset, nothing duplicated (admin/workers not re-seeded)
    assert (tmp_path / "uploads" / image).exists()

    assert b"Invalid" not in post_login(c2, "/login", "asha@test.com", "Secret123").data   # password still works
    assert code.encode() in c2.get("/my-complaints").data
    assert c2.get(f"/uploads/{image}").status_code == 200                                  # photo still served
    c2.get("/logout")
    post_login(c2, "/admin/login", "admin@civic.gov", "Admin@123")
    assert c2.get("/admin/analytics").status_code == 200
    assert code.encode() in c2.get("/admin").data
    assert b"worker.eb@civic.gov" in c2.get("/admin/workers").data
    stop(app2)
