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
    _ensure_column(inspector, 'news', 'photo_author', 'VARCHAR(255)')
    _ensure_column(inspector, 'news', 'organization', 'VARCHAR(255)')


def seed_news_taxonomy():
    """Начальное заполнение списков категорий/уровней новостей (дальше
    редактируются в админке). Срабатывает только если таблица целиком
    пуста — единоразовый бутстрап при первом запуске на чистой базе.

    Раньше значения добавлялись поштучно при каждом старте сервера —
    это ломало ручное удаление категории/уровня через админку: после
    перезапуска сервера удалённое значение возвращалось обратно, потому
    что код считал его "недостающим значением по умолчанию"."""
    if NewsCategory.query.count() == 0:
        # Значения совпадают с пунктами второй строки меню фильтра новостей
        # (routes/main.py: NEWS_MENU) — редактор выбирает категорию из этого
        # же списка в форме новости, поэтому текст должен быть один в один.
        for name in ('Официально', 'Соревнования', 'Семинары', 'Люди и даты', 'Комитеты и комиссии'):
            db.session.add(NewsCategory(name=name))

    if NewsLevel.query.count() == 0:
        for name in ('цфо', 'регион', 'отделение', 'клуб'):
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
