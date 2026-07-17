from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import unquote, urlparse


SUPPORTED_ENGINES = {"auto", "postgres", "postgresql", "mysql", "mariadb", "sqlite"}


@dataclass(frozen=True)
class DatabaseCandidate:
    engine: str
    label: str
    config: dict[str, Any]


class Database:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.instance_dir = base_dir / "instance"
        self.instance_dir.mkdir(exist_ok=True)
        self._active: DatabaseCandidate | None = None

    def health(self) -> dict[str, Any]:
        try:
            candidate = self._get_active_candidate()
            with self._connect(candidate) as connection:
                cursor = connection.cursor()
                cursor.execute(self._select_one_sql(candidate.engine))
                cursor.fetchone()
            return {"ok": True, "engine": candidate.engine, "label": candidate.label}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def create_booking(
        self,
        *,
        check_in: str,
        check_out: str,
        room_type: str,
        guests: int,
        name: str,
        email: str,
        phone: str,
    ) -> int | None:
        candidate = self._get_active_candidate()
        placeholder = self._placeholder(candidate.engine)
        sql = (
            "INSERT INTO bookings (check_in, check_out, room_type, guests, name, email, phone) "
            f"VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})"
        )
        if candidate.engine == "postgres":
            sql += " RETURNING id"

        with self._connect(candidate) as connection:
            cursor = connection.cursor()
            cursor.execute(sql, (check_in, check_out, room_type, guests, name, email, phone))
            inserted_id = self._last_insert_id(candidate.engine, cursor)
            connection.commit()
            return inserted_id

    def create_contact(self, *, name: str, email: str, message: str) -> int | None:
        candidate = self._get_active_candidate()
        placeholder = self._placeholder(candidate.engine)
        sql = (
            "INSERT INTO contacts (name, email, message) "
            f"VALUES ({placeholder}, {placeholder}, {placeholder})"
        )
        if candidate.engine == "postgres":
            sql += " RETURNING id"

        with self._connect(candidate) as connection:
            cursor = connection.cursor()
            cursor.execute(sql, (name, email, message))
            inserted_id = self._last_insert_id(candidate.engine, cursor)
            connection.commit()
            return inserted_id

    def count_bookings_by_room(self, *, check_in: str, check_out: str) -> dict[str, int]:
        candidate = self._get_active_candidate()
        placeholder = self._placeholder(candidate.engine)
        sql = (
            "SELECT room_type, COUNT(*) FROM bookings "
            f"WHERE check_in < {placeholder} AND check_out > {placeholder} "
            "GROUP BY room_type"
        )

        with self._connect(candidate) as connection:
            cursor = connection.cursor()
            cursor.execute(sql, (check_out, check_in))
            return {str(room_type).lower(): int(count) for room_type, count in cursor.fetchall()}

    def find_booking(self, *, booking_id: int, email: str) -> dict[str, Any] | None:
        candidate = self._get_active_candidate()
        placeholder = self._placeholder(candidate.engine)
        sql = (
            "SELECT id, check_in, check_out, room_type, guests, name, email, phone, created_at "
            f"FROM bookings WHERE id = {placeholder} AND email = {placeholder}"
        )

        with self._connect(candidate) as connection:
            cursor = connection.cursor()
            cursor.execute(sql, (booking_id, email))
            row = cursor.fetchone()

        if not row:
            return None

        keys = ("id", "check_in", "check_out", "room_type", "guests", "name", "email", "phone", "created_at")
        booking = dict(zip(keys, row))
        booking["id"] = int(booking["id"])
        booking["room_type"] = str(booking["room_type"]).lower()
        booking["status"] = "pending"
        return booking

    def _get_active_candidate(self) -> DatabaseCandidate:
        if self._active is not None:
            return self._active

        errors: list[str] = []

        for candidate in self._candidates():
            try:
                with self._connect(candidate) as connection:
                    self._init_schema(candidate.engine, connection)
                self._active = candidate
                return candidate
            except Exception as exc:
                errors.append(f"{candidate.label}: {exc}")

        raise RuntimeError("No usable database connection. " + " | ".join(errors))

    def _candidates(self) -> list[DatabaseCandidate]:
        candidates: list[DatabaseCandidate] = []
        database_url = os.getenv("DATABASE_URL", "").strip()

        if database_url:
            return [_candidate_from_url(database_url, self.instance_dir)]

        db_engine = os.getenv("DB_ENGINE", "auto").strip().lower() or "auto"
        if db_engine not in SUPPORTED_ENGINES:
            raise ValueError(
                "Unsupported DB_ENGINE. Use one of: auto, postgres, mysql, mariadb, sqlite."
            )

        if db_engine in {"postgres", "postgresql"}:
            candidates.append(self._postgres_candidate())
        elif db_engine in {"mysql", "mariadb"}:
            candidates.append(self._mysql_candidate())
        elif db_engine == "sqlite":
            candidates.append(self._sqlite_candidate())
        else:
            candidates.extend(self._auto_candidates())

        if _truthy(os.getenv("SQLITE_FALLBACK", "1")) and not any(c.engine == "sqlite" for c in candidates):
            candidates.append(self._sqlite_candidate())

        return candidates

    def _auto_candidates(self) -> list[DatabaseCandidate]:
        return [self._postgres_candidate(), self._mysql_candidate()]

    def _postgres_candidate(self) -> DatabaseCandidate:
        return DatabaseCandidate(
            "postgres",
            "PostgreSQL",
            {
                "host": _env("POSTGRES_HOST", "DB_HOST", default="localhost"),
                "port": int(_env("POSTGRES_PORT", "DB_PORT", default="5432")),
                "dbname": _env("POSTGRES_DB", "DB_DATABASE", default="hotel_booking"),
                "user": _env("POSTGRES_USER", "DB_USERNAME", default="postgres"),
                "password": _env("POSTGRES_PASSWORD", "DB_PASSWORD", default=""),
            },
        )

    def _mysql_candidate(self) -> DatabaseCandidate:
        return DatabaseCandidate(
            "mysql",
            "MySQL",
            {
                "host": _env("MYSQL_HOST", "DB_HOST", default="localhost"),
                "port": int(_env("MYSQL_PORT", "DB_PORT", default="3306")),
                "database": _env("MYSQL_DATABASE", "DB_DATABASE", default="hotel_booking"),
                "user": _env("MYSQL_USER", "DB_USERNAME", default="root"),
                "password": _env("MYSQL_PASSWORD", "DB_PASSWORD", default=""),
                "charset": "utf8mb4",
            },
        )

    def _sqlite_candidate(self) -> DatabaseCandidate:
        sqlite_path = _env("SQLITE_PATH", default=str(self.instance_dir / "hotel_booking.sqlite3"))
        return DatabaseCandidate("sqlite", "SQLite", {"path": sqlite_path})

    @contextmanager
    def _connect(self, candidate: DatabaseCandidate) -> Iterator[Any]:
        connection = None
        try:
            if candidate.engine == "sqlite":
                connection = sqlite3.connect(candidate.config["path"])
            elif candidate.engine == "mysql":
                import pymysql

                connection = pymysql.connect(**candidate.config)
            elif candidate.engine == "postgres":
                import psycopg

                connection = psycopg.connect(**candidate.config)
            else:
                raise ValueError(f"Unsupported database engine: {candidate.engine}")

            yield connection
        finally:
            if connection is not None:
                connection.close()

    def _init_schema(self, engine: str, connection: Any) -> None:
        cursor = connection.cursor()

        for statement in self._schema_sql(engine):
            cursor.execute(statement)

        connection.commit()

    def _schema_sql(self, engine: str) -> list[str]:
        if engine == "sqlite":
            return [
                """
                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_in DATE NOT NULL,
                    check_out DATE NOT NULL,
                    room_type TEXT NOT NULL,
                    guests INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ]

        if engine == "postgres":
            return [
                """
                CREATE TABLE IF NOT EXISTS bookings (
                    id SERIAL PRIMARY KEY,
                    check_in DATE NOT NULL,
                    check_out DATE NOT NULL,
                    room_type VARCHAR(50) NOT NULL,
                    guests INTEGER NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) NOT NULL,
                    phone VARCHAR(30) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS contacts (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ]

        return [
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                check_in DATE NOT NULL,
                check_out DATE NOT NULL,
                room_type VARCHAR(50) NOT NULL,
                guests INT NOT NULL,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) NOT NULL,
                phone VARCHAR(30) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]

    def _placeholder(self, engine: str) -> str:
        return "?" if engine == "sqlite" else "%s"

    def _select_one_sql(self, engine: str) -> str:
        return "SELECT 1"

    def _last_insert_id(self, engine: str, cursor: Any) -> int | None:
        if engine == "postgres":
            row = cursor.fetchone()
            return int(row[0]) if row else None
        if engine in {"sqlite", "mysql"}:
            return int(cursor.lastrowid)
        return None


def load_env(path: Path) -> None:
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")

        if key and key not in os.environ:
            os.environ[key] = value


def _candidate_from_url(database_url: str, instance_dir: Path) -> DatabaseCandidate:
    parsed = urlparse(database_url)
    scheme = parsed.scheme.lower()

    if scheme == "sqlite":
        path = unquote(parsed.path)
        if path in {"", "/"}:
            path = str(instance_dir / "hotel_booking.sqlite3")
        elif path.startswith("/") and parsed.netloc:
            path = f"{parsed.netloc}{path}"
        return DatabaseCandidate("sqlite", "SQLite DATABASE_URL", {"path": path})

    if scheme in {"postgres", "postgresql"}:
        return DatabaseCandidate(
            "postgres",
            "PostgreSQL DATABASE_URL",
            {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 5432,
                "dbname": parsed.path.lstrip("/") or "hotel_booking",
                "user": unquote(parsed.username or "postgres"),
                "password": unquote(parsed.password or ""),
            },
        )

    if scheme in {"mysql", "mariadb"}:
        return DatabaseCandidate(
            "mysql",
            "MySQL DATABASE_URL",
            {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 3306,
                "database": parsed.path.lstrip("/") or "hotel_booking",
                "user": unquote(parsed.username or "root"),
                "password": unquote(parsed.password or ""),
                "charset": "utf8mb4",
            },
        )

    raise ValueError(f"Unsupported DATABASE_URL scheme: {scheme}")


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _env(*keys: str, default: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value is not None and value.strip() != "":
            return value.strip()
    return default
