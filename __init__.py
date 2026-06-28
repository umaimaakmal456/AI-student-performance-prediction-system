from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv

# Load environment variables from .env (no-op if the file doesn't exist)
load_dotenv()

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "student-performance-secret-key")

    # --- Database Configuration ---
    # Primary: DATABASE_URL env var (Neon.tech PostgreSQL or any other cloud DB)
    # Fallback: local SQLite file for development / offline testing
    basedir = os.path.abspath(os.path.dirname(__file__))
    default_sqlite = "sqlite:///" + os.path.join(basedir, "assistant.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", default_sqlite)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    db.init_app(app)

    from .routes import main
    app.register_blueprint(main)
    
    with app.app_context():
        # Create all tables if they don't exist
        from . import models
        db.create_all()

    return app
