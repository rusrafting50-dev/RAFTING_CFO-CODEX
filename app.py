"""Точка входа Flask-приложения RAFTING_SITE."""
import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, render_template

from auth import create_default_admin, ensure_schema, login_manager, seed_news_taxonomy
from models import db
from routes import register_blueprints

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

RU_MONTHS_GENITIVE = {
    1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая', 6: 'июня',
    7: 'июля', 8: 'августа', 9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря',
}


def format_ru_date(value):
    """День цифрой + месяц прописью ("6 августа"); год добавляется
    цифрой только если это не текущий год ("6 августа 2025")."""
    if not value:
        return ''
    month = RU_MONTHS_GENITIVE[value.month]
    if value.year == datetime.utcnow().year:
        return f'{value.day} {month}'
    return f'{value.day} {month} {value.year}'


def format_ru_date_full(value):
    """День цифрой + месяц прописью + год всегда ("6 августа 2026") —
    для диапазонов дат (карточки соревнований), где год важен всегда,
    а не только когда он отличается от текущего."""
    if not value:
        return ''
    return f'{value.day} {RU_MONTHS_GENITIVE[value.month]} {value.year}'


def cap_first(value):
    """Первая буква прописная, остальной текст не трогаем (в отличие от
    str.capitalize(), который заодно понижает регистр всего остального —
    это ломало бы аббревиатуры вроде "ДК")."""
    text = str(value)
    if not text:
        return text
    return text[0].upper() + text[1:]


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
    app.jinja_env.filters['ru_date'] = format_ru_date
    app.jinja_env.filters['ru_date_full'] = format_ru_date_full
    app.jinja_env.filters['cap_first'] = cap_first

    register_blueprints(app)

    with app.app_context():
        db.create_all()
        ensure_schema()
        create_default_admin()
        seed_news_taxonomy()

    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}

    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5003)
