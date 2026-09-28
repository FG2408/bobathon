"""Flask application factory."""
import os
from flask import Flask


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

    from .db import init_db
    init_db(app)

    from .routes import main
    app.register_blueprint(main)

    return app
