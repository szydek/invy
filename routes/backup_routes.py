# routes/backup_routes.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
# import shutil
import sqlite3

from flask import redirect, url_for, flash, request

from config import DATABASE


def register_backup_routes(app):
    @app.post("/backup/db")
    def backup_db():
        src = Path(DATABASE)

        if not src.exists():
            flash(f"Database file not found: {src}", "error")
            return redirect(request.referrer or url_for("index"))

        backups_dir = Path("backups")
        backups_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        dst = backups_dir / f"invy-{stamp}.db"

        # Copy the database file as a snapshot
        # shutil.copy2(src, dst)
        src_conn = sqlite3.connect(str(src))
        dst_conn = sqlite3.connect(str(dst))
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()

        flash(f"DB backup created: {dst}", "success")
        return redirect(request.referrer or url_for("gear_page"))

