# routes/core_routes.py
from __future__ import annotations
from flask import render_template, redirect, url_for, jsonify, request, send_from_directory
from config import APP_DIR, QUARTZ_PUBLIC

def register_core_routes(app):
    @app.get("/routes")
    def routes():
        return "<br>".join(sorted([f"{r.rule} → {r.endpoint}" for r in app.url_map.iter_rules()]))

    @app.get("/")
    def index():
        return redirect(url_for("albums_page"))

    @app.get("/household")
    def household_page():
        return render_template("household.html")

    @app.get("/local")
    def local_page():
        return render_template("local.html")

    @app.get("/wiki")
    def wiki_page():
        return render_template("wiki.html")

    @app.get("/wiki/")
    @app.get("/wiki/<path:filename>")
    def wiki(filename: str = "index.html"):
        return send_from_directory(QUARTZ_PUBLIC, filename)

    @app.post("/savewiki")
    def save_tiddlywiki():
        try:
            updated_content = request.data.decode("utf-8")
            out_path = f"{APP_DIR}/static/tiddlywiki"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(updated_content)
            return jsonify({"status": "success", "message": "Saved successfully!"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
