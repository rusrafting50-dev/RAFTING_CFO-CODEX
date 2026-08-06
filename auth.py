"""Авторизация: Flask-Login, хэширование паролей, первый admin при первом запуске."""
from werkzeug.security import generate_password_hash
from flask_login import LoginManager

from models import NewsCategory, NewsLevel, db, User

login_manager = LoginManager()
login_manager.login_view = 'admin.login'
login_manager.login_message = 'Пожалуйста, войдите в систему для доступа к этой странице.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def _ensure_column(inspector, table, column, ddl_type):
    """Добавляет колонку в существующую таблицу, если её там ещё нет."""
    from sqlalchemy import text

    if table not in inspector.get_table_names():
        return

    existing_columns = {col['name'] for col in inspector.get_columns(table)}
    if column not in existing_columns:
        with db.engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
        print(f'[auth] В таблицу {table} добавлена колонка {column}.')


def ensure_schema():
    """Догоняет схему уже существующей базы под текущие модели.

    db.create_all() создаёт только отсутствующие таблицы и не меняет
    уже существующие — при каждом добавлении нового поля в модель сюда
    добавляется соответствующая проверка, иначе сервер, запущенный на
    базе, созданной до этого поля, падал бы при первом же обращении
    к соответствующей таблице.
    """
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    _ensure_column(inspector, 'user', 'allowed_sections', "VARCHAR(255) NOT NULL DEFAULT ''")
    _ensure_column(inspector, 'news', 'image_path', 'VARCHAR(500)')
    _ensure_column(inspector, 'news', 'description', 'TEXT')


def seed_news_taxonomy():
    """Добавляет недостающие значения в списки категорий/уровней новостей
    (дальше редактируются в админке). Сравнивается поштучно, а не только
    "таблица пуста" — иначе значения, понадобившиеся коду позже (см.
    routes/main.py: NEWS_MENU), не попадали бы в уже заполненную базу."""
    existing_categories = {c.name for c in NewsCategory.query.all()}
    for name in ('соревнование', 'мероприятие', 'федерация', 'регион', 'люди_и_даты', 'комитеты_и_комиссии'):
        if name not in existing_categories:
            db.session.add(NewsCategory(name=name))

    existing_levels = {lvl.name for lvl in NewsLevel.query.all()}
    for name in ('цфо', 'регион', 'отделение', 'клуб'):
        if name not in existing_levels:
            db.session.add(NewsLevel(name=name))

    db.session.commit()


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
