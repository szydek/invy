from __future__ import annotations

import os
from flask import redirect

def register_wiki_routes(app):
    @app.route("/wiki", endpoint="wiki_redirect")
    def wiki_redirect():
        wiki_url = os.environ.get("WIKI_URL", "http://localhost:8081")
        return redirect(wiki_url, code=302)
