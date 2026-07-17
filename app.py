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
BOOKING_STATUSES_JSON_PATH = BASE_DIR / "instance" / "booking_statuses.json"
CONTACTS_JSON_PATH = BASE_DIR / "instance" / "contacts.json"
CONTACTS_JSON_LOCK = Lock()
ROOM_INVENTORY = {
    "deluxe": 10,
    "executive": 5,
    "presidential": 2,
}
ACTIVE_BOOKING_STATUSES = {"pending", "accepted", "confirmed"}
STATUS_LABELS = {
    "pending": "Still in review",
    "accepted": "Accepted",
    "confirmed": "Accepted",
    "rejected": "Not accepted",
    "cancelled": "Cancelled",
}


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

    @app.post("/api/availability")
    def check_availability():
        payload = _request_payload()
        errors = _validate_availability(payload)

        if errors:
            return jsonify({"ok": False, "errors": errors}), 400

        availability = _availability_for_dates(
            database,
            str(payload["check_in"]),
            str(payload["check_out"]),
        )
        return jsonify({"ok": True, "rooms": availability}), 200

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
        availability = _availability_for_dates(
            database,
            booking_data["check_in"],
            booking_data["check_out"],
        )
        room_availability = availability.get(booking_data["room_type"], {})

        if int(room_availability.get("available", 0)) <= 0:
            return jsonify(
                {
                    "ok": False,
                    "errors": {
                        "room_type": "That room type is fully booked for the selected dates.",
                    },
                    "availability": availability,
                }
            ), 409

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
                "status": "pending",
                "availability": availability,
                "message": "Booking request received.",
            }
        ), 201

    @app.post("/api/bookings/status")
    def booking_status():
        payload = _request_payload()
        errors = _validate_booking_status_lookup(payload)

        if errors:
            return jsonify({"ok": False, "errors": errors}), 400

        booking = _find_booking_for_status(
            database,
            str(payload["booking_id"]).strip(),
            str(payload["email"]).strip(),
        )

        if booking is None:
            return jsonify(
                {
                    "ok": False,
                    "errors": {
                        "booking_id": "No booking found for that reference and email.",
                    },
                }
            ), 404

        status = _booking_status(booking)
        return jsonify(
            {
                "ok": True,
                "booking": _public_booking(booking, status),
                "status": status,
                "label": STATUS_LABELS.get(status, status.title()),
                "message": _status_message(status),
            }
        ), 200

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
                "status": "pending",
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


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    return data if isinstance(data, list) else []


def _booking_id_from_reference(value: Any) -> int | None:
    reference = str(value).strip()
    digits = "".join(character for character in reference if character.isdigit())

    if not digits:
        return None

    return int(digits)


def _availability_for_dates(database: Database, check_in: str, check_out: str) -> dict[str, dict[str, Any]]:
    booked_counts = {room_type: 0 for room_type in ROOM_INVENTORY}

    try:
        for room_type, count in database.count_bookings_by_room(check_in=check_in, check_out=check_out).items():
            if room_type in booked_counts:
                booked_counts[room_type] += count
    except Exception:
        pass

    for booking in _read_json_bookings():
        if not _booking_overlaps(booking, check_in, check_out):
            continue

        status = str(booking.get("status", "pending")).strip().lower() or "pending"
        room_type = str(booking.get("room_type", "")).strip().lower()

        if room_type in booked_counts and status in ACTIVE_BOOKING_STATUSES:
            booked_counts[room_type] += 1

    return {
        room_type: {
            "room_type": room_type,
            "label": _room_label(room_type),
            "total": total,
            "booked": min(booked_counts[room_type], total),
            "available": max(total - booked_counts[room_type], 0),
            "sold_out": booked_counts[room_type] >= total,
        }
        for room_type, total in ROOM_INVENTORY.items()
    }


def _booking_overlaps(booking: dict[str, Any], check_in: str, check_out: str) -> bool:
    booking_check_in = str(booking.get("check_in", ""))
    booking_check_out = str(booking.get("check_out", ""))
    return booking_check_in < check_out and booking_check_out > check_in


def _find_booking_for_status(database: Database, booking_reference: str, email: str) -> dict[str, Any] | None:
    email_key = email.strip().lower()

    for booking in _read_json_bookings():
        if not _reference_matches_booking(booking_reference, booking):
            continue

        if str(booking.get("email", "")).strip().lower() == email_key:
            return booking

    booking_id = _booking_id_from_reference(booking_reference)

    if booking_id is None:
        return None

    try:
        return database.find_booking(booking_id=booking_id, email=email.strip())
    except Exception:
        return None


def _reference_matches_booking(reference: str, booking: dict[str, Any]) -> bool:
    clean_reference = reference.strip().lower()
    booking_id = str(booking.get("id", "")).strip().lower()
    padded_reference = f"gss-{str(booking.get('id', '')).zfill(4)}".lower()
    return clean_reference in {booking_id, padded_reference}


def _booking_status(booking: dict[str, Any]) -> str:
    override = _booking_status_override(booking)

    if override:
        return override

    return str(booking.get("status", "pending")).strip().lower() or "pending"


def _booking_status_override(booking: dict[str, Any]) -> str | None:
    overrides = _read_json_list(BOOKING_STATUSES_JSON_PATH)
    booking_id = str(booking.get("id", "")).strip().lower()
    booking_reference = _booking_reference(booking.get("id")).strip().lower()
    email = str(booking.get("email", "")).strip().lower()

    for override in reversed(overrides):
        reference = str(override.get("booking_id", override.get("booking_reference", ""))).strip().lower()
        override_email = str(override.get("email", "")).strip().lower()
        status = str(override.get("status", "")).strip().lower()

        if reference in {booking_id, booking_reference} and override_email == email and status:
            return status

    return None


def _public_booking(booking: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "id": booking.get("id"),
        "reference": _booking_reference(booking.get("id")),
        "status": status,
        "status_label": STATUS_LABELS.get(status, status.title()),
        "check_in": str(booking.get("check_in", "")),
        "check_out": str(booking.get("check_out", "")),
        "room_type": str(booking.get("room_type", "")),
        "room_label": _room_label(str(booking.get("room_type", ""))),
        "guests": booking.get("guests"),
        "name": booking.get("name"),
    }


def _booking_reference(booking_id: Any) -> str:
    if str(booking_id).upper().startswith("LOCAL-"):
        return str(booking_id)

    try:
        return f"GSS-{int(booking_id):04d}"
    except (TypeError, ValueError):
        return str(booking_id or "Pending")


def _room_label(room_type: str) -> str:
    return {
        "deluxe": "Deluxe Room",
        "executive": "Executive Suite",
        "presidential": "Presidential Suite",
    }.get(room_type, room_type.title())


def _status_message(status: str) -> str:
    if status in {"accepted", "confirmed"}:
        return "Your booking request was accepted. Your room is still okay."
    if status == "rejected":
        return "Your booking request was not accepted. Please choose another room or contact the hotel."
    if status == "cancelled":
        return "This booking is cancelled."
    return "Your booking request is still waiting for hotel approval."


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


def _validate_availability(payload: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}

    for field in ("check_in", "check_out"):
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

    return errors


def _validate_booking_status_lookup(payload: dict[str, Any]) -> dict[str, str]:
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
