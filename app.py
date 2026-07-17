from __future__ import annotations

import logging
import json
from datetime import date, datetime, timezone
from email.utils import parseaddr
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request

from database import Database, load_env


BASE_DIR = Path(__file__).resolve().parent
BOOKINGS_JSON_PATH = BASE_DIR / "instance" / "bookings.json"
BOOKINGS_JSON_LOCK = Lock()
BOOKING_CONFIRMATIONS_JSON_PATH = BASE_DIR / "instance" / "booking_confirmations.json"
BOOKING_CONFIRMATIONS_JSON_LOCK = Lock()
CONTACTS_JSON_PATH = BASE_DIR / "instance" / "contacts.json"
CONTACTS_JSON_LOCK = Lock()


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

        booking_data = {
            "check_in": payload["check_in"],
            "check_out": payload["check_out"],
            "room_type": payload["room_type"].strip().lower(),
            "guests": int(payload["guests"]),
            "name": payload["name"].strip(),
            "email": payload["email"].strip(),
            "phone": payload["phone"].strip(),
        }

        try:
            booking_id = database.create_booking(**booking_data)
            storage = "database"
        except Exception as exc:
            app.logger.warning("Database booking save failed; using JSON fallback: %s", exc)
            booking_id = _save_booking_to_json(booking_data)
            storage = "json"

        _log_booking_created(app, booking_id, payload)
        return jsonify(
            {
                "ok": True,
                "id": booking_id,
                "storage": storage,
                "message": "Booking request received.",
            }
        ), 201

    @app.post("/api/bookings/confirm")
    def confirm_booking():
        payload = _request_payload()
        errors = _validate_booking_confirmation(payload)

        if errors:
            return jsonify({"ok": False, "errors": errors}), 400

        confirmation = _save_booking_confirmation(
            {
                "booking_id": _booking_id_from_reference(payload["booking_id"]),
                "booking_reference": str(payload["booking_id"]).strip(),
                "email": payload["email"].strip(),
                "storage": str(payload.get("storage", "unknown")).strip() or "unknown",
            }
        )

        return jsonify(
            {
                "ok": True,
                "id": confirmation["id"],
                "status": "confirmed",
                "message": "Booking confirmed.",
            }
        ), 201

    @app.post("/api/contact")
    def create_contact():
        payload = _request_payload()
        errors = _validate_contact(payload)

        if errors:
            return jsonify({"ok": False, "errors": errors}), 400

        contact_data = {
            "name": payload["name"].strip(),
            "email": payload["email"].strip(),
            "message": payload["message"].strip(),
        }

        try:
            contact_id = database.create_contact(**contact_data)
            storage = "database"
        except Exception as exc:
            app.logger.warning("Database contact save failed; using JSON fallback: %s", exc)
            contact_id = _save_contact_to_json(contact_data)
            storage = "json"

        return jsonify(
            {
                "ok": True,
                "id": contact_id,
                "storage": storage,
                "message": "Message received.",
            }
        ), 201

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


def _save_booking_to_json(booking_data: dict[str, Any]) -> int:
    with BOOKINGS_JSON_LOCK:
        BOOKINGS_JSON_PATH.parent.mkdir(exist_ok=True)
        bookings = _read_json_bookings()
        next_id = _next_json_booking_id(bookings)
        bookings.append(
            {
                "id": next_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                **booking_data,
            }
        )
        BOOKINGS_JSON_PATH.write_text(json.dumps(bookings, indent=2), encoding="utf-8")
        return next_id


def _read_json_bookings() -> list[dict[str, Any]]:
    if not BOOKINGS_JSON_PATH.is_file():
        return []

    try:
        data = json.loads(BOOKINGS_JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    return data if isinstance(data, list) else []


def _next_json_booking_id(bookings: list[dict[str, Any]]) -> int:
    numeric_ids: list[int] = []

    for item in bookings:
        try:
            numeric_ids.append(int(item.get("id", 0)))
        except (TypeError, ValueError):
            continue

    return max(numeric_ids, default=0) + 1


def _save_booking_confirmation(confirmation_data: dict[str, Any]) -> dict[str, Any]:
    with BOOKING_CONFIRMATIONS_JSON_LOCK:
        BOOKING_CONFIRMATIONS_JSON_PATH.parent.mkdir(exist_ok=True)
        confirmations = _read_json_list(BOOKING_CONFIRMATIONS_JSON_PATH)
        existing = _find_existing_confirmation(confirmations, confirmation_data)

        if existing is not None:
            existing["status"] = "confirmed"
            existing["confirmed_at"] = datetime.now(timezone.utc).isoformat()
            BOOKING_CONFIRMATIONS_JSON_PATH.write_text(
                json.dumps(confirmations, indent=2),
                encoding="utf-8",
            )
            _mark_json_booking_confirmed(confirmation_data)
            return existing

        confirmation = {
            "id": _next_numeric_json_id(confirmations),
            "status": "confirmed",
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
            **confirmation_data,
        }
        confirmations.append(confirmation)
        BOOKING_CONFIRMATIONS_JSON_PATH.write_text(
            json.dumps(confirmations, indent=2),
            encoding="utf-8",
        )
        _mark_json_booking_confirmed(confirmation_data)
        return confirmation


def _find_existing_confirmation(
    confirmations: list[dict[str, Any]],
    confirmation_data: dict[str, Any],
) -> dict[str, Any] | None:
    booking_reference = str(confirmation_data["booking_reference"]).strip().lower()
    email = str(confirmation_data["email"]).strip().lower()

    for confirmation in confirmations:
        if (
            str(confirmation.get("booking_reference", "")).strip().lower() == booking_reference
            and str(confirmation.get("email", "")).strip().lower() == email
        ):
            return confirmation

    return None


def _mark_json_booking_confirmed(confirmation_data: dict[str, Any]) -> None:
    booking_id = confirmation_data.get("booking_id")

    if booking_id is None:
        return

    with BOOKINGS_JSON_LOCK:
        bookings = _read_json_bookings()
        changed = False

        for booking in bookings:
            if booking.get("id") != booking_id:
                continue

            if str(booking.get("email", "")).strip().lower() != str(confirmation_data["email"]).strip().lower():
                continue

            booking["status"] = "confirmed"
            booking["confirmed_at"] = datetime.now(timezone.utc).isoformat()
            changed = True
            break

        if changed:
            BOOKINGS_JSON_PATH.write_text(json.dumps(bookings, indent=2), encoding="utf-8")


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    return data if isinstance(data, list) else []


def _next_numeric_json_id(items: list[dict[str, Any]]) -> int:
    numeric_ids: list[int] = []

    for item in items:
        try:
            numeric_ids.append(int(item.get("id", 0)))
        except (TypeError, ValueError):
            continue

    return max(numeric_ids, default=0) + 1


def _booking_id_from_reference(value: Any) -> int | None:
    reference = str(value).strip()
    digits = "".join(character for character in reference if character.isdigit())

    if not digits:
        return None

    return int(digits)


def _save_contact_to_json(contact_data: dict[str, Any]) -> int:
    with CONTACTS_JSON_LOCK:
        CONTACTS_JSON_PATH.parent.mkdir(exist_ok=True)
        contacts = _read_json_contacts()
        next_id = _next_json_contact_id(contacts)
        contacts.append(
            {
                "id": next_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                **contact_data,
            }
        )
        CONTACTS_JSON_PATH.write_text(json.dumps(contacts, indent=2), encoding="utf-8")
        return next_id


def _read_json_contacts() -> list[dict[str, Any]]:
    if not CONTACTS_JSON_PATH.is_file():
        return []

    try:
        data = json.loads(CONTACTS_JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    return data if isinstance(data, list) else []


def _next_json_contact_id(contacts: list[dict[str, Any]]) -> int:
    numeric_ids: list[int] = []

    for item in contacts:
        try:
            numeric_ids.append(int(item.get("id", 0)))
        except (TypeError, ValueError):
            continue

    return max(numeric_ids, default=0) + 1


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


def _validate_booking_confirmation(payload: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}

    if not str(payload.get("booking_id", "")).strip():
        errors["booking_id"] = "Booking reference is required."

    if not str(payload.get("email", "")).strip():
        errors["email"] = "Email is required."
    elif not _valid_email(payload["email"]):
        errors["email"] = "Use a valid email address."

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
