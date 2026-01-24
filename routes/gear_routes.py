# routes/gear_routes.py
from __future__ import annotations

from typing import Any
from flask import render_template, request, redirect, url_for, flash, Response, jsonify

import csv
import io
from datetime import datetime

from db import get_db
from util import _clean, _int, _float


FORMATS = ["Eurorack", "Desktop", "Pedal", "Rack", "Tape", "Software"]
RIGS = ["Main", "Portable", "Spare"]


def _build_gear_query():
    """Build the same query/params logic as gear_page so export matches the current filter."""
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
    return sql, params, {"q": q, "format": fmt, "rig": rig, "purchase_source": src}


def register_gear_routes(app):
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

        flash(
            "Updated gear item." if cur.rowcount else "Gear item not found.",
            "success" if cur.rowcount else "error",
        )
        return redirect(url_for("gear_page"))

    @app.post("/gear/<int:gear_id>/delete")
    def gear_delete(gear_id: int):
        db = get_db()
        cur = db.execute("DELETE FROM studio_gear WHERE id = ?", (gear_id,))
        db.commit()
        flash(
            "Deleted gear item." if cur.rowcount else "Gear item not found.",
            "success" if cur.rowcount else "error",
        )
        return redirect(url_for("gear_page"))

    @app.get("/gear/export.json")
    def gear_export_json():
        db = get_db()
        sql, params, filters = _build_gear_query()
        rows = db.execute(sql, params).fetchall()

        payload = {
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "count": len(rows),
            "filters": filters,
            "items": [dict(r) for r in rows],
        }
        return jsonify(payload)

    @app.get("/gear/export.csv")
    def gear_export_csv():
        db = get_db()
        sql, params, filters = _build_gear_query()
        rows = db.execute(sql, params).fetchall()

        columns = [
            "id",
            "brand",
            "name_model",
            "format",
            "hp",
            "quantity",
            "rig",
            "functions",
            "purchase_source",
            "seller_listing",
            "purchase_price",
            "value",
            "year_built",
            "notes",
            "updated_at",
        ]

        output = io.StringIO()
        writer = csv.writer(output)

        stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
        writer.writerow([f"# exported_at={stamp}"])
        writer.writerow([f"# filters={filters}"])
        writer.writerow([])

        writer.writerow(columns)
        for r in rows:
            d = dict(r)
            writer.writerow([d.get(c, "") for c in columns])

        csv_text = output.getvalue()
        output.close()

        filename_stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        filename = f"gear-export-{filename_stamp}.csv"

        return Response(
            csv_text,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
