"""
manage_data.py -- inspect, back up and recover Smart Civic Reporter data.
Uses only the Python standard library. Run from the project folder:

    python manage_data.py where            show the permanent data folder + record counts
    python manage_data.py backup           make a timestamped backup right now
    python manage_data.py find             search Downloads/Desktop/Documents/OneDrive for old civic.db files
    python manage_data.py import "<path>"  copy an old civic.db (and its uploads) into the permanent folder

Nothing here ever deletes data. 'import' first backs up the current database and
refuses to replace a database that has MORE records than the one you import
(add --force to override).
"""
import shutil
import sys
from pathlib import Path

import storage


def cmd_where():
    d = storage.get_data_dir()
    rows = storage.count_rows(d / storage.DB_FILENAME)
    print("Permanent data folder :", d)
    print("Database              :", d / storage.DB_FILENAME)
    print("Records               :", rows if rows else "database not created yet")
    print("Uploads folder        :", d / "uploads", f"({len(list((d / 'uploads').glob('*')))} files)")
    print("Backups folder        :", d / "backups", f"({len(list((d / 'backups').glob('civic_*.db')))} backups)")


def cmd_backup():
    d = storage.get_data_dir()
    b = storage.backup_db(d, force=True)
    print("Backup written:", b if b else "nothing to back up yet (no database)")


def cmd_find():
    home = Path.home()
    roots = [home / "Downloads", home / "Desktop", home / "Documents", home / "OneDrive",
             home / "OneDrive" / "Desktop", home / "OneDrive" / "Documents"]
    seen, found = set(), []
    for root in roots:
        if root.is_dir():
            for p in root.rglob("civic.db"):
                rp = p.resolve()
                if rp not in seen:
                    seen.add(rp)
                    found.append(rp)
    perm = storage.get_data_dir() / storage.DB_FILENAME
    if perm.exists():
        found.append(perm.resolve())
    if not found:
        print("No civic.db files found in Downloads/Desktop/Documents/OneDrive.")
        return
    print(f"{'users':>6} {'complaints':>10}  modified             path")
    for p in sorted(found, key=lambda x: x.stat().st_mtime, reverse=True):
        r = storage.count_rows(p) or {"users": "?", "complaints": "?"}
        mtime = __import__("datetime").datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        tag = "  <-- CURRENT permanent database" if p == perm.resolve() else ""
        print(f"{r['users']!s:>6} {r['complaints']!s:>10}  {mtime}  {p}{tag}")


def cmd_import(path, force=False):
    src = Path(path)
    if not src.is_file():
        sys.exit(f"Not found: {src}")
    d = storage.get_data_dir()
    target = d / storage.DB_FILENAME
    s_rows = storage.count_rows(src)
    if s_rows is None:
        sys.exit("That file is not a readable SQLite database.")
    t_rows = storage.count_rows(target)
    if t_rows and not force:
        if (t_rows["users"] + t_rows["complaints"]) > (s_rows["users"] + s_rows["complaints"]):
            sys.exit(f"Refusing: current database has MORE records ({t_rows}) than the one you are "
                     f"importing ({s_rows}). Use --force if you are sure.")
    if target.exists():
        print("Backed up current database first:", storage.backup_db(d, force=True))
    shutil.copy2(src, target)
    print(f"Imported {src} -> {target}  ({s_rows['users']} users, {s_rows['complaints']} complaints)")
    for uploads in (src.parent / "static" / "uploads", src.parent / "uploads"):
        for msg in storage.migrate_legacy_data(d, None, uploads):
            print(msg)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv
    if not args or args[0] == "where":
        cmd_where()
    elif args[0] == "backup":
        cmd_backup()
    elif args[0] == "find":
        cmd_find()
    elif args[0] == "import" and len(args) > 1:
        cmd_import(args[1], force)
    else:
        print(__doc__)
