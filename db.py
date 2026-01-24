# db.py
from __future__ import annotations

import sqlite3
from typing import Optional
from flask import g

from config import DATABASE


def get_db() -> sqlite3.Connection:
    """One shared sqlite connection per request."""
    if "db" not in g:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


def close_db(exc: Optional[BaseException]) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Initialize all tables."""
    db = get_db()

    # Albums table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist TEXT NOT NULL,
            title TEXT NOT NULL,
            release_date TEXT,
            genre TEXT,
            stream_link TEXT,
            notes TEXT,
            mp3_file TEXT,
            copies INTEGER DEFAULT 1,
            formats TEXT,
            cover_image TEXT
        )
        """
    )

    # Studio Gear table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS studio_gear (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_model TEXT NOT NULL,
            brand TEXT,
            format TEXT,
            hp INTEGER,
            purchase_source TEXT,
            seller_listing TEXT,
            functions TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            rig TEXT,
            value REAL,
            purchase_price REAL,
            year_built INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )

    # Indexes for Studio Gear
    db.execute("CREATE INDEX IF NOT EXISTS idx_sg_name ON studio_gear(name_model)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_sg_brand ON studio_gear(brand)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_sg_format ON studio_gear(format)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_sg_rig ON studio_gear(rig)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_sg_source ON studio_gear(purchase_source)")

    db.commit()
