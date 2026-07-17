# Hotel Booking

A simple hotel booking website now backed by Flask.

## Project Structure

- `app.py` contains the Flask page routes and JSON API endpoints.
- `database.py` manages PostgreSQL, MySQL/MariaDB, and local SQLite fallback connections.
- `run.py` starts the Flask development server.
- `templates/` contains the HTML pages rendered by Flask.
- `static/` contains CSS, JavaScript, and image assets.
- `sql/` contains the database dump.

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and update database values if needed.
4. Start the Flask app:

   ```bash
   python run.py
   ```

5. Visit `http://127.0.0.1:5000/`.

If PostgreSQL or MySQL is configured and reachable, the backend will use it and create the required `bookings` and `contacts` tables. If not, `DB_ENGINE=auto` can fall back to `instance/hotel_booking.sqlite3` for local development.

Bookings have an extra JSON fallback: if the Flask app is running but the database cannot save, booking requests are appended to `instance/bookings.json`. If the booking page is opened while Flask is not running, the browser saves the booking JSON in local storage under `gss_hotel_offline_bookings` so the user still gets a confirmation.

## Database Options

Use `DB_ENGINE` to choose the backend. `DB_ENGINE=auto` tries PostgreSQL first, then MySQL/MariaDB, then SQLite fallback when `SQLITE_FALLBACK=1`.

```env
DB_ENGINE=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=hotel_booking
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

```env
DB_ENGINE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=hotel_booking
MYSQL_USER=root
MYSQL_PASSWORD=your_password
```

You can also force either backend with `DATABASE_URL`:

```env
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/hotel_booking
DATABASE_URL=mysql://root:your_password@localhost:3306/hotel_booking
```

Set `SQLITE_FALLBACK=0` if you want startup to fail when the configured PostgreSQL/MySQL database is unavailable.

## API

- `GET /api/health` checks the application database connection.
- `POST /api/bookings` creates a booking request.
- `POST /api/contact` stores a contact message.
