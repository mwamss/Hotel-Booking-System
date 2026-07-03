from __future__ import annotations

import logging
from datetime import date
from email.utils import parseaddr
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request

from database import Database, load_env


BASE_DIR = Path(__file__).resolve().parent


def create_app() -> Flask:
    load_env(BASE_DIR / ".env")

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.logger.setLevel(logging.INFO)
    database = Database(BASE_DIR)

    @app.after_request
    def add_local_cors_headers(response):
        origin = request.headers.get("Origin", "")

        if request.path.startswith("/api/") and _is_local_browser_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Vary"] = "Origin"

        return response

    @app.get("/")
    @app.get("/index.html")
    def home():
        return render_template("index.html")

    @app.get("/about.html")
    def about():
        return render_template("about.html")

    @app.get("/booking.html")
    def booking():
        return render_template("booking.html")

    @app.get("/contact.html")
    def contact():
        return render_template("contact.html")

    @app.get("/api/health")
    def health():
        db_status = database.health()
        status_code = 200 if db_status["ok"] else 503
        return jsonify({"ok": db_status["ok"], "database": db_status}), status_code

    @app.post("/api/bookings")
    def create_booking():
        payload = _request_payload()
        errors = _validate_booking(payload)

        if errors:
            return jsonify({"ok": False, "errors": errors}), 400

        booking_id = database.create_booking(
            check_in=payload["check_in"],
            check_out=payload["check_out"],
            room_type=payload["room_type"],
            guests=int(payload["guests"]),
            name=payload["name"].strip(),
            email=payload["email"].strip(),
            phone=payload["phone"].strip(),
        )
        _log_booking_created(app, booking_id, payload)
        return jsonify({"ok": True, "id": booking_id, "message": "Booking request received."}), 201

    @app.post("/api/contact")
    def create_contact():
        payload = _request_payload()
        errors = _validate_contact(payload)

        if errors:
            return jsonify({"ok": False, "errors": errors}), 400

        contact_id = database.create_contact(
            name=payload["name"].strip(),
            email=payload["email"].strip(),
            message=payload["message"].strip(),
        )
        return jsonify({"ok": True, "id": contact_id, "message": "Message received."}), 201

    return app


def _request_payload() -> dict[str, Any]:
    if request.is_json:
        payload = dict(request.get_json(silent=True) or {})
    else:
        payload = dict(request.form)

    return {key.replace("-", "_"): value for key, value in payload.items()}


def _log_booking_created(app: Flask, booking_id: int | None, payload: dict[str, Any]) -> None:
    app.logger.info(
        "Booking created: id=%s, name=%s, email=%s, phone=%s, room=%s, guests=%s, check_in=%s, check_out=%s",
        booking_id or "unknown",
        _clean_log_value(payload["name"]),
        _clean_log_value(payload["email"]),
        _clean_log_value(payload["phone"]),
        _clean_log_value(payload["room_type"]),
        _clean_log_value(payload["guests"]),
        _clean_log_value(payload["check_in"]),
        _clean_log_value(payload["check_out"]),
    )


def _clean_log_value(value: Any) -> str:
    return " ".join(str(value).strip().split())


def _is_local_browser_origin(origin: str) -> bool:
    if origin == "null":
        return True

    parsed = urlparse(origin)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }


def _validate_booking(payload: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    required_fields = ("check_in", "check_out", "room_type", "guests", "name", "email", "phone")

    for field in required_fields:
        if not str(payload.get(field, "")).strip():
            errors[field] = "This field is required."

    if errors:
        return errors

    check_in = _parse_date(payload["check_in"])
    check_out = _parse_date(payload["check_out"])

    if check_in is None:
        errors["check_in"] = "Use a valid check-in date."
    if check_out is None:
        errors["check_out"] = "Use a valid check-out date."
    if check_in and check_out and check_out <= check_in:
        errors["check_out"] = "Check-out must be after check-in."

    try:
        guests = int(payload["guests"])
    except (TypeError, ValueError):
        errors["guests"] = "Guests must be a number."
    else:
        if guests < 1 or guests > 10:
            errors["guests"] = "Guests must be between 1 and 10."

    if not _valid_email(payload["email"]):
        errors["email"] = "Use a valid email address."

    if len(str(payload["phone"]).strip()) < 7:
        errors["phone"] = "Use a valid phone number."

    allowed_rooms = {"deluxe", "executive", "presidential"}
    if str(payload["room_type"]).strip().lower() not in allowed_rooms:
        errors["room_type"] = "Choose a valid room type."

    return errors


def _validate_contact(payload: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}

    for field in ("name", "email", "message"):
        if not str(payload.get(field, "")).strip():
            errors[field] = "This field is required."

    if "email" not in errors and not _valid_email(payload["email"]):
        errors["email"] = "Use a valid email address."

    if "message" not in errors and len(str(payload["message"]).strip()) < 5:
        errors["message"] = "Message is too short."

    return errors


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _valid_email(value: Any) -> bool:
    parsed = parseaddr(str(value).strip())[1]
    return "@" in parsed and "." in parsed.rsplit("@", 1)[-1]


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
