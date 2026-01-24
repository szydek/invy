from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional
from flask import Blueprint, g, render_template, request, redirect, url_for, flash


studio_gear_bp = Blueprint("studio_gear", __name__, url_prefix="/studio-gear")

# If Invy already has a DB helper, replace get_db() with your existing one.
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect("albums.db")  # IMPORTANT: set to your Invy DB path
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


FORMATS = ["Eurorack", "Desktop", "Pedal", "Rack", "Tape", "Software"]
RIGS = ["Main", "Portable", "Spare"]


def init_studio_gear_table() -> None:
    db = get_db()
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
        );
        """
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_sg_name ON studio_gear(name_model);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_sg_brand ON studio_gear(brand);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_sg_format ON studio_gear(format);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_sg_rig ON studio_gear(rig);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_sg_source ON studio_gear(purchase_source);")
    db.commit()


@studio_gear_bp.before_app_request
def _ensure_table() -> None:
    # Runs before each request; safe because CREATE TABLE IF NOT EXISTS is cheap.
    init_studio_gear_table()


def _clean_text(v: str) -> str:
    return (v or "").strip()

def _parse_int(v: str) -> Optional[int]:
    s = (v or "").strip()
    if s == "":
        return None
    return int(s)

def _parse_float(v: str) -> Optional[float]:
    s = (v or "").strip().replace("$", "").replace(",", "")
    if s == "":
        return None
    return float(s)


@studio_gear_bp.get("/")
def list_gear():
    q = _clean_text(request.args.get("q", ""))
    fmt = _clean_text(request.args.get("format", ""))
    rig = _clean_text(request.args.get("rig", ""))
    src = _clean_text(request.args.get("purchase_source", ""))

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

    db = get_db()
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
        "gear_list.html",
        items=items,
        q=q,
        fmt=fmt,
        rig=rig,
        src=src,
        formats=FORMATS,
        rigs=RIGS,
        sources=sources,
    )


@studio_gear_bp.get("/new")
def new_gear():
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


def _from_form(form) -> Dict[str, Any]:
    name_model = _clean_text(form.get("name_model", ""))
    if not name_model:
        name_model = "(Unnamed)"
        flash("Name / Model is required.", "error")

    hp = None
    try:
        hp = _parse_int(form.get("hp", ""))
    except ValueError:
        flash("HP must be an integer.", "error")

    quantity = 1
    try:
        quantity = _parse_int(form.get("quantity", "")) or 1
    except ValueError:
        quantity = 1
        flash("Quantity must be an integer.", "error")

    value = None
    try:
        value = _parse_float(form.get("value", ""))
    except ValueError:
        flash("Value must be numeric.", "error")

    purchase_price = None
    try:
        purchase_price = _parse_float(form.get("purchase_price", ""))
    except ValueError:
        flash("Purchase Price must be numeric.", "error")

    year_built = None
    try:
        year_built = _parse_int(form.get("year_built", ""))
    except ValueError:
        flash("Year Built must be an integer (e.g. 2021).", "error")

    return {
        "name_model": name_model,
        "brand": _clean_text(form.get("brand", "")),
        "format": _clean_text(form.get("format", "")),
        "hp": hp,
        "purchase_source": _clean_text(form.get("purchase_source", "")),
        "seller_listing": _clean_text(form.get("seller_listing", "")),
        "functions": _clean_text(form.get("functions", "")),
        "quantity": quantity,
        "rig": _clean_text(form.get("rig", "")),
        "value": value,
        "purchase_price": purchase_price,
        "year_built": year_built,
        "notes": _clean_text(form.get("notes", "")),
    }


@studio_gear_bp.post("/")
def create_gear():
    data = _from_form(request.form)
    db = get_db()
    db.execute(
        """
        INSERT INTO studio_gear (
            name_model, brand, format, hp, purchase_source, seller_listing, functions,
            quantity, rig, value, purchase_price, year_built, notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            data["name_model"], data["brand"], data["format"], data["hp"],
            data["purchase_source"], data["seller_listing"], data["functions"],
            data["quantity"], data["rig"], data["value"], data["purchase_price"],
            data["year_built"], data["notes"],
        ),
    )
    db.commit()
    flash("Added gear item.", "success")
    return redirect(url_for("studio_gear.list_gear"))


@studio_gear_bp.get("/<int:gear_id>/edit")
def edit_gear(gear_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM studio_gear WHERE id = ?", (gear_id,)).fetchone()
    if not row:
        flash("Item not found.", "error")
        return redirect(url_for("studio_gear.list_gear"))
    return render_template("gear_form.html", item=dict(row), formats=FORMATS, rigs=RIGS, mode="edit")


@studio_gear_bp.post("/<int:gear_id>")
def update_gear(gear_id: int):
    data = _from_form(request.form)
    db = get_db()
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
            data["name_model"], data["brand"], data["format"], data["hp"],
            data["purchase_source"], data["seller_listing"], data["functions"],
            data["quantity"], data["rig"], data["value"], data["purchase_price"],
            data["year_built"], data["notes"], gear_id,
        ),
    )
    db.commit()
    flash("Updated gear item." if cur.rowcount else "Item not found.", "success" if cur.rowcount else "error")
    return redirect(url_for("studio_gear.list_gear"))


@studio_gear_bp.post("/<int:gear_id>/delete")
def delete_gear(gear_id: int):
    db = get_db()
    cur = db.execute("DELETE FROM studio_gear WHERE id = ?", (gear_id,))
    db.commit()
    flash("Deleted gear item." if cur.rowcount else "Item not found.", "success" if cur.rowcount else "error")
    return redirect(url_for("studio_gear.list_gear"))
