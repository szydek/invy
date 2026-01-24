# routes/discogs_routes.py
from __future__ import annotations

import os
from typing import Optional

import requests
from flask import jsonify, request

from config import (
    DISCOGS_API_TOKEN,
    DISCOGS_USER_AGENT,
    DISCOGS_USERNAME,
    DISCOGS_API_URL,
    DISCOGS_API_USER_URL,
    THUMBNAIL_FOLDER,
)
from db import get_db
from util import safe_filename


def register_discogs_routes(app):
    @app.route("/sync_collection", methods=["POST"])
    def sync_collection():
        if not DISCOGS_USERNAME or not DISCOGS_API_TOKEN:
            return jsonify({"success": False, "message": "Missing DISCOGS_USERNAME or DISCOGS_API_TOKEN"}), 400

        username = DISCOGS_USERNAME
        headers = {"User-Agent": DISCOGS_USER_AGENT}
        params = {"token": DISCOGS_API_TOKEN}

        page = 1
        total_pages = 1

        try:
            while page <= total_pages:
                response = requests.get(
                    f"{DISCOGS_API_USER_URL}/{username}/collection/folders/0/releases",
                    headers=headers,
                    params={**params, "page": page, "per_page": 50},
                    timeout=30,
                )
                if response.status_code != 200:
                    return jsonify({"success": False, "message": "Error fetching collection", "discogs": response.text}), 500

                data = response.json()
                total_pages = data["pagination"]["pages"]

                db = get_db()
                for release in data["releases"]:
                    artist = release["basic_information"]["artists"][0]["name"]
                    title = release["basic_information"]["title"]
                    release_date = release["basic_information"].get("year", None)
                    genre = release["basic_information"].get("genres", [None])[0]
                    cover_url = release["basic_information"].get("cover_image")

                    existing = db.execute(
                        "SELECT id FROM albums WHERE artist = ? AND title = ?",
                        (artist, title),
                    ).fetchone()

                    if not existing:
                        db.execute(
                            "INSERT INTO albums (artist, title, release_date, genre) VALUES (?, ?, ?, ?)",
                            (artist, title, release_date, genre),
                        )
                        db.commit()
                        if cover_url:
                            download_thumbnail(artist, title, cover_url)

                page += 1

            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

    @app.route("/fetch_discogs", methods=["GET"])
    def fetch_discogs():
        artist = request.args.get("artist")
        title = request.args.get("title")

        if not DISCOGS_API_TOKEN:
            return jsonify({"success": False, "error": "Missing DISCOGS_API_TOKEN"}), 400

        if not artist or not title:
            return jsonify({"success": False, "error": "Missing artist or title."}), 400

        params = {
            "artist": artist,
            "release_title": title,
            "type": "master",
            "token": DISCOGS_API_TOKEN,
        }

        response = requests.get(DISCOGS_API_URL, params=params, timeout=30)
        if response.status_code == 200:
            results = response.json().get("results")
            if results:
                result = results[0]
                return jsonify(
                    {
                        "success": True,
                        "artist": result.get("artist"),
                        "title": result.get("title"),
                        "release_date": result.get("year"),
                        "genre": result.get("genre", [""])[0],
                        "album_cover": result.get("cover_image"),
                    }
                )

        return jsonify({"success": False, "error": "No results found."})

    @app.route("/fetch_thumbnail", methods=["POST"])
    def fetch_thumbnail():
        """Fetch a thumbnail from Discogs for a given artist and title and save to static/thumbnails."""
        try:
            data = request.get_json() or {}
            artist = data.get("artist")
            title = data.get("title")

            if not artist or not title:
                return jsonify({"success": False, "error": "Artist and title are required."}), 400

            thumbnail_url = fetch_thumbnail_from_discogs(artist, title)
            if not thumbnail_url:
                return jsonify({"success": False, "error": "No thumbnail found on Discogs."}), 404

            return download_thumbnail(artist, title, thumbnail_url)

        except Exception:
            return jsonify({"success": False, "error": "An unexpected error occurred."}), 500


def fetch_thumbnail_from_discogs(artist: str, title: str) -> Optional[str]:
    """Return a thumbnail URL (prefers master primary image when possible)."""
    if not DISCOGS_API_TOKEN:
        return None

    params = {
        "artist": artist,
        "title": title,
        "format": "album",
        "type": "release",
        "token": DISCOGS_API_TOKEN,
    }

    try:
        response = requests.get(DISCOGS_API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("results"):
            results = data["results"]

            for result in results:
                master_id = result.get("master_id")
                if master_id and master_id != 0:
                    master_api_url = f"https://api.discogs.com/masters/{master_id}"
                    master_resp = requests.get(
                        master_api_url,
                        headers={"Authorization": f"Discogs token={DISCOGS_API_TOKEN}"},
                        timeout=30,
                    )
                    master_resp.raise_for_status()
                    master_data = master_resp.json()

                    images = master_data.get("images") or []
                    for image in images:
                        if image.get("type") == "primary" and image.get("uri"):
                            return image["uri"]
                    if images and images[0].get("uri"):
                        return images[0]["uri"]

            for result in results:
                if result.get("thumb"):
                    return result["thumb"]

        return None

    except Exception:
        return None


def download_thumbnail(artist: str, title: str, thumbnail_url: str):
    """Download a thumbnail and update DB cover_image filename."""
    try:
        headers = {"User-Agent": DISCOGS_USER_AGENT}
        resp = requests.get(thumbnail_url, headers=headers, stream=True, timeout=30)

        if resp.status_code != 200:
            return jsonify({"success": False, "error": "Failed to download thumbnail."}), 500

        filename = f"{safe_filename(artist)}_{safe_filename(title)}.jpg"
        local_path = os.path.join(THUMBNAIL_FOLDER, filename)

        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(1024):
                if chunk:
                    f.write(chunk)

        db = get_db()
        row = db.execute("SELECT id FROM albums WHERE artist = ? AND title = ?", (artist, title)).fetchone()
        if not row:
            return jsonify({"success": False, "error": "Album not found in database."}), 404

        db.execute("UPDATE albums SET cover_image = ? WHERE id = ?", (filename, row["id"]))
        db.commit()

        return jsonify({"success": True, "thumbnail_path": local_path}), 200

    except Exception:
        return jsonify({"success": False, "error": "An unexpected error occurred."}), 500
