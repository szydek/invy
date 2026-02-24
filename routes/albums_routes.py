# routes/albums_routes.py
from __future__ import annotations

import os
import json
import re
from typing import Any

from flask import render_template, request, redirect, url_for, current_app

from db import get_db
from util import safe_filename
from config import THUMBNAIL_FOLDER
import routes.discogs_routes as discogs


AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aiff", ".aif"}


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s

def _list_audio_dir() -> list[str]:
    """
    Return audio file paths *relative* to /static/audio, recursively.
    Example: "Samhain/Initium/01 Initium.m4a"
    """
    root = os.path.join(current_app.static_folder, "audio")
    if not os.path.isdir(root):
        return []

    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # skip hidden dirs
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        for name in filenames:
            if name.startswith("."):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in AUDIO_EXTS:
                continue

            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)          # Artist/Album/Track.ext
            rel = rel.replace(os.sep, "/")             # normalize for URLs/templates
            files.append(rel)

    return sorted(files, key=lambda s: s.lower())

def _match_album_audio_files(all_files: list[str], artist: str, title: str) -> list[str]:
    """
    Match files by directory structure:
      /static/audio/<Artist>/<Album>/<Track>
    all_files entries are relative paths like "Artist/Album/Track.ext".
    """
    artist_key = _norm(artist)
    album_key = _norm(title)

    exact: list[str] = []
    fuzzy: list[str] = []

    for rel in all_files:
        parts = rel.split("/")
        if len(parts) < 3:
            continue

        rel_artist, rel_album = parts[0], parts[1]
        ra = _norm(rel_artist)
        rb = _norm(rel_album)

        # exact normalized match
        if ra == artist_key and rb == album_key:
            exact.append(rel)
            continue

        # fuzzy fallback (helps when titles differ slightly: deluxe, punctuation, etc.)
        if ra == artist_key and (rb.startswith(album_key) or album_key.startswith(rb) or album_key in rb):
            fuzzy.append(rel)

    return exact if exact else fuzzy

def get_existing_artists_and_genres():
    db = get_db()
    artists = [
        r["artist"]
        for r in db.execute("SELECT DISTINCT artist FROM albums ORDER BY artist").fetchall()
    ]
    genres = [
        r["genre"]
        for r in db.execute("SELECT DISTINCT genre FROM albums ORDER BY genre").fetchall()
    ]
    return artists, genres


def register_albums_routes(app):
    @app.route("/albums")
    def albums_page():
        db = get_db()
        rows = db.execute("SELECT * FROM albums ORDER BY artist, title").fetchall()

        albums: dict[str, list[dict[str, Any]]] = {}
        genres = set()

        # Build artist -> albums list (your template expects this)
        for row in rows:
            artist = row["artist"]
            genre = (row["genre"] or "").strip()
            if genre:
                genres.add(genre)

            formats = []
            if row["formats"] and isinstance(row["formats"], str):
                try:
                    formats = json.loads(row["formats"])
                except Exception:
                    formats = []

            album = {
                "id": row["id"],
                "artist": artist,
                "title": row["title"],
                "release_date": row["release_date"],
                "genre": row["genre"],
                "stream_link": row["stream_link"],
                "notes": row["notes"],
                "mp3_file": row["mp3_file"],  # legacy single-file support (optional)
                "formats": formats,
                "cover_image": row["cover_image"],
            }
            albums.setdefault(artist, []).append(album)

        unique_genres = sorted(genres, key=lambda s: s.lower())

        # Attach audio_files per album by matching directory structure in /static/audio
        all_audio_files = _list_audio_dir()
        for artist_name, albums_by_artist in albums.items():
            for a in albums_by_artist:
                a["audio_files"] = _match_album_audio_files(
                    all_audio_files,
                    a.get("artist", artist_name),
                    a.get("title", ""),
                )
                # Debug (optional)
                # print(a["artist"], "-", a["title"], "=>", len(a["audio_files"]), a["audio_files"][:5])

        return render_template("albums.html", albums=albums, unique_genres=unique_genres)

    @app.route("/add", methods=["GET", "POST"])
    def add_album():
        if request.method == "POST":
            artist = request.form["artist"]
            title = request.form["title"]
            release_date = request.form.get("release_date", "")
            genre = request.form.get("genre", "")
            stream_link = request.form.get("stream_link", "")
            notes = request.form.get("notes", "")
            cover_url = request.form.get("cover_url", "")

            mp3_file = request.files.get("mp3_file")
            mp3_filename = None
            if mp3_file and mp3_file.filename and mp3_file.filename.lower().endswith(".mp3"):
                mp3_filename = f"{artist}-{title}.mp3".replace(" ", "_")
                mp3_path = os.path.join(app.config["UPLOAD_FOLDER"], mp3_filename)
                mp3_file.save(mp3_path)

            selected_formats = request.form.getlist("formats")
            formats_json = json.dumps(selected_formats) if selected_formats else json.dumps([])

            db = get_db()
            db.execute(
                """
                INSERT INTO albums (artist, title, release_date, genre, formats, stream_link, mp3_file, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (artist, title, release_date, genre, formats_json, stream_link, mp3_filename, notes),
            )
            db.commit()

            if cover_url:
                discogs.download_thumbnail(artist, title, cover_url)

            return redirect(url_for("albums_page"))

        artists, genres = get_existing_artists_and_genres()
        return render_template("add.html", artists=artists, genres=genres)

    @app.route("/edit/<int:album_id>", methods=["GET", "POST"])
    def edit_album(album_id: int):
        db = get_db()

        if request.method == "POST":
            artist = request.form["artist"]
            title = request.form["title"]
            release_date = request.form.get("release_date", "")
            genre = request.form.get("genre", "")
            stream_link = request.form.get("stream_link", "")
            notes = request.form.get("notes", "")

            # Cover image handling
            if request.form.get("fetch_cover") == "on":
                cover_image_path = fetch_thumbnail_from_discogs(artist, title)
            else:
                row = db.execute("SELECT cover_image FROM albums WHERE id = ?", (album_id,)).fetchone()
                cover_image_path = row["cover_image"] if row else None

            # MP3 handling
            mp3_file = request.files.get("mp3_file")
            if mp3_file and mp3_file.filename and mp3_file.filename.lower().endswith(".mp3"):
                mp3_filename = f"{artist}-{title}.mp3".replace(" ", "_")
                mp3_path = os.path.join(app.config["UPLOAD_FOLDER"], mp3_filename)
                mp3_file.save(mp3_path)
            else:
                row = db.execute("SELECT mp3_file FROM albums WHERE id = ?", (album_id,)).fetchone()
                mp3_filename = row["mp3_file"] if row else None

            # Formats handling
            selected_formats = request.form.getlist("formats")
            if selected_formats:
                formats_json = json.dumps(selected_formats)
            else:
                row = db.execute("SELECT formats FROM albums WHERE id = ?", (album_id,)).fetchone()
                formats_json = row["formats"] if row else json.dumps([])

            db.execute(
                """
                UPDATE albums
                SET artist = ?, title = ?, release_date = ?, genre = ?, stream_link = ?, notes = ?,
                    mp3_file = ?, formats = ?, cover_image = ?
                WHERE id = ?
                """,
                (artist, title, release_date, genre, stream_link, notes, mp3_filename, formats_json, cover_image_path, album_id),
            )
            db.commit()
            return redirect(url_for("albums_page"))

        row = db.execute("SELECT * FROM albums WHERE id = ?", (album_id,)).fetchone()
        if not row:
            return "Album not found", 404

        formats = []
        if row["formats"] and isinstance(row["formats"], str):
            try:
                formats = json.loads(row["formats"])
            except Exception:
                formats = []

        artists, genres = get_existing_artists_and_genres()

        album_data = {
            "id": row["id"],
            "artist": row["artist"],
            "title": row["title"],
            "release_date": row["release_date"],
            "genre": row["genre"],
            "stream_link": row["stream_link"],
            "notes": row["notes"],
            "mp3_file": row["mp3_file"],
            "formats": formats,
            "cover_image": row["cover_image"],
        }

        return render_template("edit.html", album=album_data, artists=artists, genres=genres)

    @app.route("/delete/<int:album_id>", methods=["POST"])
    def delete_album(album_id: int):
        db = get_db()
        row = db.execute("SELECT mp3_file FROM albums WHERE id = ?", (album_id,)).fetchone()

        mp3_filename = row["mp3_file"] if row else None
        mp3_path = os.path.join(app.config["UPLOAD_FOLDER"], mp3_filename) if mp3_filename else None

        db.execute("DELETE FROM albums WHERE id = ?", (album_id,))
        db.commit()

        # delete file if exists
        if mp3_path and os.path.exists(mp3_path):
            try:
                os.remove(mp3_path)
            except Exception:
                pass

        return redirect(url_for("albums_page"))
    