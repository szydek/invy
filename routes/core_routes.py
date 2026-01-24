# routes/core_routes.py
from __future__ import annotations

import os
from flask import render_template, redirect, url_for, jsonify, request, send_from_directory

from config import APP_DIR, QUARTZ_PUBLIC


def register_core_routes(app):
    @app.get("/routes")
    def routes():
        return "<br>".join(sorted([f"{r.rule} → {r.endpoint}" for r in app.url_map.iter_rules()]))

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
