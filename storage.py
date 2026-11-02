"""
storage.py -- permanent data location for Smart Civic Reporter.

Problem this solves
-------------------
The app used to keep civic.db and the uploaded photos/voice notes INSIDE the
project folder. Every time the project was re-extracted into a new folder
(or civic.db was deleted to "start fresh"), the app started with a brand new,
empty database -- so every account and complaint looked like it had vanished.

Now all persistent data lives in ONE fixed folder that does not depend on where
the project is extracted:

    Windows : C:\\Users\\<you>\\AppData\\Local\\SmartCivicReporter\\
                 civic.db      <- every table: users (citizens/workers/admin),
                                  complaints, status history, feedback,
                                  notifications, green points
                 uploads\\      <- complaint photos and voice notes
                 backups\\      <- automatic timestamped copies of civic.db

Override with the CIVIC_DATA_DIR environment variable if you prefer another place.

This module uses only the Python standard library, and it NEVER deletes or
overwrites a database that already contains data.
"""
import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

APP_FOLDER_NAME = "SmartCivicReporter"
DB_FILENAME = "civic.db"
KEEP_BACKUPS = 30


def get_data_dir(override=None) -> Path:
    """Return (and create) the permanent data directory."""
    if override:
        base = Path(override)
    elif os.environ.get("CIVIC_DATA_DIR"):
        base = Path(os.environ["CIVIC_DATA_DIR"])
    else:
        root = (os.environ.get("LOCALAPPDATA")
                or os.environ.get("XDG_DATA_HOME")
                or str(Path.home() / ".local" / "share"))
        base = Path(root) / APP_FOLDER_NAME
    base = base.expanduser().resolve()
    (base / "uploads").mkdir(parents=True, exist_ok=True)
    (base / "backups").mkdir(parents=True, exist_ok=True)
    return base


def sqlite_uri(db_path: Path) -> str:
    """Absolute SQLAlchemy URI. as_posix() avoids backslash/escape problems on Windows."""
    return "sqlite:///" + Path(db_path).resolve().as_posix()


def count_rows(db_path):
    """Return {'users': n, 'complaints': n} read-only, or None if unreadable/missing."""
    db_path = Path(db_path)
    if not db_path.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            out = {}
            for table in ("users", "complaints"):
                try:
                    out[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except sqlite3.DatabaseError:
                    out[table] = 0
            return out
        finally:
            con.close()
    except sqlite3.DatabaseError:
        return None


def migrate_legacy_data(data_dir: Path, legacy_db, legacy_uploads):
    """
    One-time, copy-only migration from the old in-project location.
    - Copies legacy civic.db ONLY if the permanent database does not exist yet.
    - Copies legacy uploads that are not already present. Nothing is ever deleted
      and an existing permanent database is never touched.
    Returns a list of human-readable messages.
    """
    messages = []
    target_db = data_dir / DB_FILENAME

    legacy_db = Path(legacy_db) if legacy_db else None
    if not target_db.exists() and legacy_db and legacy_db.exists():
        rows = count_rows(legacy_db)
        if rows is not None:
            shutil.copy2(legacy_db, target_db)
            messages.append(f"Copied existing database from {legacy_db} "
                            f"({rows['users']} users, {rows['complaints']} complaints) "
                            f"-> {target_db}")

    legacy_uploads = Path(legacy_uploads) if legacy_uploads else None
    if legacy_uploads and legacy_uploads.is_dir():
        copied = 0
        for f in legacy_uploads.iterdir():
            if f.is_file() and f.name != ".gitkeep":
                dest = data_dir / "uploads" / f.name
                if not dest.exists():
                    shutil.copy2(f, dest)
                    copied += 1
        if copied:
            messages.append(f"Copied {copied} existing upload(s) into {data_dir / 'uploads'}")
    return messages


def backup_db(data_dir: Path, force=False, min_age_seconds=30):
    """
    Make a consistent timestamped copy of civic.db using SQLite's online-backup API
    (safe even while the app is running). Keeps the newest KEEP_BACKUPS copies.
    Returns the backup path, or None if skipped.
    """
    src = data_dir / DB_FILENAME
    backups = data_dir / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        return None

    existing = sorted(backups.glob("civic_*.db"))
    if existing and not force:
        if time.time() - existing[-1].stat().st_mtime < min_age_seconds:
            return None  # debug auto-reloader starts the app twice; don't double-backup

    # microseconds in the name -> unique and correctly sortable even for back-to-back backups
    dest = backups / f"civic_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.db"

    s = sqlite3.connect(str(src))
    d = sqlite3.connect(str(dest))
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()

    # prune only OLD backups; the one just written is never a candidate
    for old in sorted(p for p in backups.glob("civic_*.db") if p != dest)[:-(KEEP_BACKUPS - 1) or None]:
        try:
            old.unlink()
        except OSError:
            pass
    return dest
