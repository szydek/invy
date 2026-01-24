# routes/backup_routes.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil

from flask import redirect, url_for, flash

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
        shutil.copy2(src, dst)

        flash(f"DB backup created: {dst}", "success")
        return redirect(url_for("routes"))
