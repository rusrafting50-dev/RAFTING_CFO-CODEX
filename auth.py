"""Авторизация: Flask-Login, хэширование паролей, первый admin при первом запуске."""
from werkzeug.security import generate_password_hash
from flask_login import LoginManager

from models import db, User

login_manager = LoginManager()
login_manager.login_view = 'admin.login'
login_manager.login_message = 'Пожалуйста, войдите в систему для доступа к этой странице.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def ensure_user_table_columns():
    """Добавляет в существующую таблицу user колонки, которых там ещё нет.

    db.create_all() создаёт только отсутствующие таблицы и не меняет
    уже существующие — на сайте, запущенном до появления поля
    allowed_sections, старая таблица user иначе не соответствовала бы
    модели, и сервер падал бы при первом же обращении к пользователям.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if 'user' not in inspector.get_table_names():
        return

    existing_columns = {col['name'] for col in inspector.get_columns('user')}
    if 'allowed_sections' not in existing_columns:
        with db.engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE user ADD COLUMN allowed_sections VARCHAR(255) NOT NULL DEFAULT ''"
            ))
        print('[auth] В таблицу user добавлена колонка allowed_sections.')


def create_default_admin():
    """Создаёт первого администратора, если в базе ещё нет ни одного пользователя."""
    if User.query.count() > 0:
        return

    admin = User(
        username='admin',
        password_hash=generate_password_hash('admin123'),
        role='admin',
        is_active=True,
    )
    db.session.add(admin)
    db.session.commit()
    print(
        '[auth] Создан администратор по умолчанию: логин "admin", пароль "admin123". '
        'Смените пароль после первого входа!'
    )
