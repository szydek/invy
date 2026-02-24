# app.py
from __future__ import annotations

import os
from flask import Flask, render_template

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


import time
import feedparser

_HEADLINES_CACHE = {"ts": 0.0, "items": []}

def get_top_headlines() -> list[dict]:
    # Use a reliable feed (BBC is usually solid)
    rss_url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(rss_url)

    items: list[dict] = []
    for e in feed.entries[:15]:
        items.append({
            "title": (e.get("title") or "").strip(),
            "link": e.get("link"),
            "published": e.get("published") or e.get("updated") or "",
        })
    return items


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
    
    @app.context_processor
    def inject_headlines():
        now = time.time()
        if now - _HEADLINES_CACHE["ts"] > 600:  # 10 min cache
            try:
                _HEADLINES_CACHE["items"] = get_top_headlines()
                _HEADLINES_CACHE["ts"] = now
            except Exception as e:
                print("HEADLINES ERROR:", e)
                _HEADLINES_CACHE["items"] = []
        return {"headlines": _HEADLINES_CACHE["items"]}

    @app.route("/player")
    def player_page():
        return render_template("player.html")


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
