from __future__ import annotations

import os
import re
import json
import sqlite3
import unicodedata
from typing import Any, Optional

import requests
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    send_from_directory,
    flash,
    g,
)

# -----------------------------
# App setup
# -----------------------------
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

app = Flask(__name__)
app.secret_key = os.getenv("INVY_SECRET_KEY", "dev-change-me")  # needed for flash messages
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
os.makedirs(QUARTZ_PUBLIC, exist_ok=True)


# -----------------------------
# DB helpers
# -----------------------------
def get_db() -> sqlite3.Connection:
    """One shared sqlite connection per request."""
    if "db" not in g:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
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

    # Studio Gear table (new)
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


@app.before_request
def _ensure_db() -> None:
    init_db()


# -----------------------------
# Utility helpers
# -----------------------------
def safe_filename(text: str, max_length: int = 120) -> str:
    """Convert text into a filesystem-safe filename."""
    if not text:
        return "file"
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[\\/\\\\]+", "_", text)
    text = re.sub(r"[^a-zA-Z0-9._-]+", "_", text)
    return text.strip("_")[:max_length]


def _clean(v: Any) -> str:
    return (v or "").strip()


def _int(v: Any) -> Optional[int]:
    s = _clean(v)
    if not s:
        return None
    return int(s)


def _float(v: Any) -> Optional[float]:
    s = _clean(v).replace("$", "").replace(",", "")
    if not s:
        return None
    return float(s)


# -----------------------------
# Debug
# -----------------------------
@app.get("/routes")
def routes():
    return "<br>".join(sorted([f"{r.rule} → {r.endpoint}" for r in app.url_map.iter_rules()]))


# -----------------------------
# Home / basic sections
# -----------------------------
@app.route("/")
def index():
    return redirect(url_for("albums_page"))


@app.route("/household")
def household_page():
    return render_template("household.html")


@app.route("/local")
def local_page():
    return render_template("local.html")


@app.route("/wiki")
def wiki_page():
    return render_template("wiki.html")


# Serve published wiki content (Quartz or similar)
@app.route("/wiki/")
@app.route("/wiki/<path:filename>")
def wiki(filename: str = "index.html"):
    return send_from_directory(QUARTZ_PUBLIC, filename)


@app.route("/savewiki", methods=["POST"])
def save_tiddlywiki():
    """Handle saving edits to a single-file wiki if you're using that flow."""
    try:
        updated_content = request.data.decode("utf-8")
        out_path = os.path.join(APP_DIR, "static", "tiddlywiki")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(updated_content)
        return jsonify({"status": "success", "message": "Saved successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# -----------------------------
# Albums
# -----------------------------
def get_existing_artists_and_genres():
    db = get_db()
    artists = [r["artist"] for r in db.execute("SELECT DISTINCT artist FROM albums ORDER BY artist").fetchall()]
    genres = [r["genre"] for r in db.execute("SELECT DISTINCT genre FROM albums ORDER BY genre").fetchall()]
    return artists, genres


@app.route("/albums")
def albums_page():
    db = get_db()
    rows = db.execute("SELECT * FROM albums ORDER BY artist, title").fetchall()

    albums: dict[str, list[dict[str, Any]]] = {}
    genres = set()

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
            "title": row["title"],
            "release_date": row["release_date"],
            "genre": row["genre"],
            "stream_link": row["stream_link"],
            "notes": row["notes"],
            "mp3_file": row["mp3_file"],
            "formats": formats,
            "cover_image": row["cover_image"],
        }
        albums.setdefault(artist, []).append(album)

    unique_genres = sorted(genres, key=lambda s: s.lower())
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
            download_thumbnail(artist, title, cover_url)

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


# -----------------------------
# Studio Gear (upgraded /gear)
# -----------------------------
FORMATS = ["Eurorack", "Desktop", "Pedal", "Rack", "Tape", "Software"]
RIGS = ["Main", "Portable", "Spare"]


@app.get("/gear")
def gear_page():
    db = get_db()

    q = _clean(request.args.get("q"))
    fmt = _clean(request.args.get("format"))
    rig = _clean(request.args.get("rig"))
    src = _clean(request.args.get("purchase_source"))

    sql = "SELECT * FROM studio_gear WHERE 1=1"
    params: list[Any] = []

    if q:
        like = f"%{q}%"
        sql += " AND (name_model LIKE ? OR brand LIKE ? OR functions LIKE ? OR notes LIKE ?)"
        params.extend([like, like, like, like])
    if fmt:
        sql += " AND format = ?"
        params.append(fmt)
    if rig:
        sql += " AND rig = ?"
        params.append(rig)
    if src:
        sql += " AND purchase_source = ?"
        params.append(src)

    sql += " ORDER BY lower(brand), lower(name_model)"
    items = db.execute(sql, params).fetchall()

    sources = [
        r["purchase_source"]
        for r in db.execute(
            """
            SELECT DISTINCT purchase_source
            FROM studio_gear
            WHERE purchase_source IS NOT NULL AND purchase_source != ''
            ORDER BY lower(purchase_source)
            """
        ).fetchall()
    ]

    return render_template(
        "gear.html",
        items=items,
        q=q,
        fmt=fmt,
        rig=rig,
        src=src,
        formats=FORMATS,
        rigs=RIGS,
        sources=sources,
    )


@app.get("/gear/new")
def gear_new():
    item = {
        "id": None,
        "name_model": "",
        "brand": "",
        "format": "",
        "hp": "",
        "purchase_source": "",
        "seller_listing": "",
        "functions": "",
        "quantity": 1,
        "rig": "",
        "value": "",
        "purchase_price": "",
        "year_built": "",
        "notes": "",
    }
    return render_template("gear_form.html", item=item, formats=FORMATS, rigs=RIGS, mode="new")


@app.post("/gear")
def gear_create():
    db = get_db()
    form = request.form

    name_model = _clean(form.get("name_model"))
    if not name_model:
        flash("Name / Model is required.", "error")
        return redirect(url_for("gear_new"))

    try:
        hp = _int(form.get("hp"))
        quantity = _int(form.get("quantity")) or 1
        value = _float(form.get("value"))
        purchase_price = _float(form.get("purchase_price"))
        year_built = _int(form.get("year_built"))
    except ValueError:
        flash("Numeric field error (HP / Qty / Value / Purchase Price / Year).", "error")
        return redirect(url_for("gear_new"))

    db.execute(
        """
        INSERT INTO studio_gear (
            name_model, brand, format, hp, purchase_source, seller_listing, functions,
            quantity, rig, value, purchase_price, year_built, notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            name_model,
            _clean(form.get("brand")),
            _clean(form.get("format")),
            hp,
            _clean(form.get("purchase_source")),
            _clean(form.get("seller_listing")),
            _clean(form.get("functions")),
            quantity,
            _clean(form.get("rig")),
            value,
            purchase_price,
            year_built,
            _clean(form.get("notes")),
        ),
    )
    db.commit()
    flash("Added gear item.", "success")
    return redirect(url_for("gear_page"))


@app.get("/gear/<int:gear_id>/edit")
def gear_edit(gear_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM studio_gear WHERE id = ?", (gear_id,)).fetchone()
    if not row:
        flash("Gear item not found.", "error")
        return redirect(url_for("gear_page"))
    return render_template("gear_form.html", item=dict(row), formats=FORMATS, rigs=RIGS, mode="edit")


@app.post("/gear/<int:gear_id>")
def gear_update(gear_id: int):
    db = get_db()
    form = request.form

    name_model = _clean(form.get("name_model"))
    if not name_model:
        flash("Name / Model is required.", "error")
        return redirect(url_for("gear_edit", gear_id=gear_id))

    try:
        hp = _int(form.get("hp"))
        quantity = _int(form.get("quantity")) or 1
        value = _float(form.get("value"))
        purchase_price = _float(form.get("purchase_price"))
        year_built = _int(form.get("year_built"))
    except ValueError:
        flash("Numeric field error (HP / Qty / Value / Purchase Price / Year).", "error")
        return redirect(url_for("gear_edit", gear_id=gear_id))

    cur = db.execute(
        """
        UPDATE studio_gear
        SET
            name_model = ?, brand = ?, format = ?, hp = ?,
            purchase_source = ?, seller_listing = ?, functions = ?,
            quantity = ?, rig = ?, value = ?, purchase_price = ?,
            year_built = ?, notes = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (
            name_model,
            _clean(form.get("brand")),
            _clean(form.get("format")),
            hp,
            _clean(form.get("purchase_source")),
            _clean(form.get("seller_listing")),
            _clean(form.get("functions")),
            quantity,
            _clean(form.get("rig")),
            value,
            purchase_price,
            year_built,
            _clean(form.get("notes")),
            gear_id,
        ),
    )
    db.commit()

    flash("Updated gear item." if cur.rowcount else "Gear item not found.", "success" if cur.rowcount else "error")
    return redirect(url_for("gear_page"))


@app.post("/gear/<int:gear_id>/delete")
def gear_delete(gear_id: int):
    db = get_db()
    cur = db.execute("DELETE FROM studio_gear WHERE id = ?", (gear_id,))
    db.commit()
    flash("Deleted gear item." if cur.rowcount else "Gear item not found.", "success" if cur.rowcount else "error")
    return redirect(url_for("gear_page"))


# -----------------------------
# Discogs integrations
# -----------------------------
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


if __name__ == "__main__":
    # init_db is handled by before_request, but this ensures the DB exists even before first request
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=8080, debug=True)
