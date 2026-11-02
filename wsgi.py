"""
wsgi.py -- entry point for a production WSGI server (gunicorn, waitress, etc.).

Local development uses `python app.py` (Flask's built-in dev server).
Deployment uses this file instead, e.g.:
    gunicorn wsgi:app
"""
from app import create_app, seed_defaults

app = create_app()
seed_defaults(app)
