"""Точка входа Flask-приложения RAFTING_SITE."""
import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask

from auth import create_default_admin, login_manager
from models import db
from routes import register_blueprints

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', f"sqlite:///{os.path.join(BASE_DIR, 'shared.db')}"
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 МБ на загружаемый файл

    db.init_app(app)
    login_manager.init_app(app)

    register_blueprints(app)

    with app.app_context():
        db.create_all()
        create_default_admin()

    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5003)
