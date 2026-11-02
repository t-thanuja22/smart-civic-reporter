"""Persistence tests for storage.py -- stdlib only, no Flask needed.
Run: python -m pytest tests/test_storage.py -v     (or: python tests/test_storage.py)"""
import os, sqlite3, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import storage


def make_db(path, users=3, complaints=2):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    con.execute("CREATE TABLE complaints (id INTEGER PRIMARY KEY, code TEXT)")
    con.executemany("INSERT INTO users(name) VALUES (?)", [(f"u{i}",) for i in range(users)])
    con.executemany("INSERT INTO complaints(code) VALUES (?)", [(f"SCR-{i}",) for i in range(complaints)])
    con.commit(); con.close()


def test_data_dir_is_fixed_and_independent_of_project_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("CIVIC_DATA_DIR", raising=False)
    a = storage.get_data_dir()
    b = storage.get_data_dir()           # "second run from another project folder"
    assert a == b == (tmp_path / "SmartCivicReporter").resolve()
    assert (a / "uploads").is_dir() and (a / "backups").is_dir()


def test_sqlite_uri_is_absolute_posix(tmp_path):
    uri = storage.sqlite_uri(tmp_path / "civic.db")
    assert uri.startswith("sqlite:///") and "\\" not in uri


def test_legacy_database_and_uploads_are_copied_not_moved(tmp_path):
    data = storage.get_data_dir(tmp_path / "data")
    legacy = tmp_path / "old"; (legacy / "static" / "uploads").mkdir(parents=True)
    make_db(legacy / "civic.db", users=5, complaints=4)
    (legacy / "static" / "uploads" / "a.jpg").write_bytes(b"img")
    msgs = storage.migrate_legacy_data(data, legacy / "civic.db", legacy / "static" / "uploads")
    assert msgs
    assert storage.count_rows(data / "civic.db") == {"users": 5, "complaints": 4}
    assert (data / "uploads" / "a.jpg").read_bytes() == b"img"
    assert (legacy / "civic.db").exists() and (legacy / "static" / "uploads" / "a.jpg").exists()


def test_existing_permanent_database_is_never_overwritten(tmp_path):
    data = storage.get_data_dir(tmp_path / "data")
    make_db(data / "civic.db", users=10, complaints=7)
    legacy = tmp_path / "old"; legacy.mkdir()
    make_db(legacy / "civic.db", users=1, complaints=0)
    storage.migrate_legacy_data(data, legacy / "civic.db", None)
    assert storage.count_rows(data / "civic.db") == {"users": 10, "complaints": 7}


def test_restart_keeps_records(tmp_path):
    """Write, 'stop the app', reopen the same fixed file -> records still there."""
    data = storage.get_data_dir(tmp_path / "data")
    make_db(data / "civic.db", users=2, complaints=2)
    con = sqlite3.connect(data / "civic.db")
    con.execute("INSERT INTO complaints(code) VALUES ('SCR-NEW')"); con.commit(); con.close()
    # restart: new process would call get_data_dir() again and open the same path
    data2 = storage.get_data_dir(tmp_path / "data")
    assert data2 == data
    assert storage.count_rows(data2 / "civic.db") == {"users": 2, "complaints": 3}


def test_backup_is_consistent_and_pruned(tmp_path, monkeypatch):
    data = storage.get_data_dir(tmp_path / "data")
    make_db(data / "civic.db", users=4, complaints=6)
    monkeypatch.setattr(storage, "KEEP_BACKUPS", 3)
    paths = [storage.backup_db(data, force=True) for _ in range(5)]
    assert all(paths)
    assert paths[-1].exists()                       # the newest backup is never pruned
    assert not paths[0].exists()                    # oldest ones were pruned
    assert storage.count_rows(paths[-1]) == {"users": 4, "complaints": 6}
    assert len(list((data / "backups").glob("civic_*.db"))) == 3
    assert storage.backup_db(data) is None   # throttled (reloader double-start)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
