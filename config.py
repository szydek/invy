# config.py
from __future__ import annotations

import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.getenv("INVY_DB_PATH", os.path.join(APP_DIR, "albums.db"))

UPLOAD_FOLDER = os.path.join(APP_DIR, "static", "audio")
THUMBNAIL_FOLDER = os.path.join(APP_DIR, "static", "thumbnails")

# Quartz / wiki published directory (so /wiki/<file> works without crashing)
QUARTZ_PUBLIC = os.getenv("QUARTZ_PUBLIC", os.path.join(APP_DIR, "static", "wiki_public"))

DISCOGS_API_TOKEN = os.getenv("DISCOGS_API_TOKEN")
DISCOGS_USER_AGENT = os.getenv("DISCOGS_USER_AGENT", "invy/0.1")
DISCOGS_USERNAME = os.getenv("DISCOGS_USERNAME")
DISCOGS_API_URL = "https://api.discogs.com/database/search"
DISCOGS_API_USER_URL = "https://api.discogs.com/users"

SECRET_KEY = os.getenv("INVY_SECRET_KEY", "dev-change-me")
