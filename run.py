import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes", "on"}
    app.run(host="127.0.0.1", port=5000, debug=debug, use_reloader=False)
