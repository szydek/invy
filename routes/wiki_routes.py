from __future__ import annotations

from pathlib import Path
from flask import (
    render_template,
    send_from_directory,
    abort,
    send_file,
    request,
    jsonify,
)

def register_wiki_routes(app):
    # ✅ Always resolve relative to the Flask app root, not the shell CWD
    BASE_DIR = Path(app.root_path).resolve()
    WIKI_DIR = (BASE_DIR / "wiki").resolve()
    WIKI_INDEX = WIKI_DIR / "index.html"

    @app.get("/wiki", endpoint="wiki_home")
    def wiki_home():
        return render_template("wiki_shell.html")

    @app.get("/wiki/index.html", endpoint="wiki_index")
    def wiki_index():
        if not WIKI_INDEX.exists():
            abort(404)

        resp = send_file(WIKI_INDEX)
        # ✅ prevent stale content after saves
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/wiki/<path:filename>", endpoint="wiki_file")
    def wiki_file(filename: str):
        if not WIKI_DIR.exists() or not WIKI_DIR.is_dir():
            abort(404)

        resp = send_from_directory(str(WIKI_DIR), filename)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.post("/savewiki", endpoint="savewiki")
    def savewiki():
        html = request.get_data(as_text=True)
        if not html or "<html" not in html.lower():
            return jsonify({"ok": False, "error": "Invalid HTML"}), 400

        WIKI_DIR.mkdir(parents=True, exist_ok=True)
        WIKI_INDEX.write_text(html, encoding="utf-8")

        stat = WIKI_INDEX.stat()
        return jsonify(
            {
                "ok": True,
                "saved_to": str(WIKI_INDEX),
                "bytes": len(html.encode("utf-8")),
                "mtime": stat.st_mtime,
            }
        )