# app.py
from __future__ import annotations

import os
from flask import Flask

from config import (
    UPLOAD_FOLDER,
    THUMBNAIL_FOLDER,
    QUARTZ_PUBLIC,
    SECRET_KEY,
)
from db import init_db, close_db

from routes.core_routes import register_core_routes
from routes.albums_routes import register_albums_routes
from routes.gear_routes import register_gear_routes
from routes.discogs_routes import register_discogs_routes
from routes.backup_routes import register_backup_routes
from routes.wiki_routes import register_wiki_routes




def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = SECRET_KEY
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

    # Ensure directories exist (same behavior as before)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
    os.makedirs(QUARTZ_PUBLIC, exist_ok=True)

    # DB lifecycle (same behavior as before)
    app.teardown_appcontext(close_db)

    @app.before_request
    def _ensure_db() -> None:
        init_db()

    # Register route groups (no blueprints; endpoints preserved)
    register_core_routes(app)
    register_albums_routes(app)
    register_gear_routes(app)
    register_discogs_routes(app)
    register_backup_routes(app)
    register_wiki_routes(app)



    return app


app = create_app()

if __name__ == "__main__":
    # same as your current bottom block
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=8080, debug=True)
