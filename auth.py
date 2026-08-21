"""Авторизация: Flask-Login, хэширование паролей, первый admin при первом запуске."""
from werkzeug.security import generate_password_hash
from flask_login import LoginManager

from models import DocumentCategory, NewsCategory, NewsLevel, db, User

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


def _ensure_nullable(inspector, table, column):
    """Снимает ограничение NOT NULL с колонки на уже существующей базе.

    SQLite не поддерживает ALTER COLUMN — таблица пересоздаётся заново по
    текущей модели (штатный для SQLite приём) с переносом всех данных;
    вызывать после того, как _ensure_column догнал остальные колонки этой
    же таблицы, иначе список колонок старой и новой таблицы разойдётся."""
    from sqlalchemy import inspect, text

    if table not in inspector.get_table_names():
        return

    # Свежий inspector, а не переданный: SQLAlchemy кэширует get_columns()
    # по таблице, а колонки этой же таблицы могли только что добавиться
    # через _ensure_column — с кэшем INSERT ниже потерял бы их.
    columns = inspect(db.engine).get_columns(table)
    col = next((c for c in columns if c['name'] == column), None)
    if col is None or col['nullable']:
        return

    column_names = ', '.join(c['name'] for c in columns)
    with db.engine.begin() as conn:
        conn.execute(text('PRAGMA foreign_keys=OFF'))
        conn.execute(text(f'ALTER TABLE {table} RENAME TO {table}_old'))
        db.metadata.tables[table].create(bind=conn)
        conn.execute(text(f'INSERT INTO {table} ({column_names}) SELECT {column_names} FROM {table}_old'))
        conn.execute(text(f'DROP TABLE {table}_old'))
        conn.execute(text('PRAGMA foreign_keys=ON'))
    print(f'[auth] В таблице {table} снято ограничение NOT NULL с колонки {column}.')


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
    _ensure_column(inspector, 'user', 'region', 'VARCHAR(255)')
    _ensure_column(inspector, 'news', 'image_path', 'VARCHAR(500)')
    _ensure_column(inspector, 'news', 'description', 'TEXT')
    _ensure_column(inspector, 'news', 'photo_author', 'VARCHAR(255)')
    _ensure_column(inspector, 'news', 'organization', 'VARCHAR(255)')
    _ensure_column(inspector, 'competition', 'age_group', 'VARCHAR(255)')
    _ensure_column(inspector, 'competition', 'boat_class', 'VARCHAR(20)')
    _ensure_column(inspector, 'competition', 'head_judge', 'VARCHAR(255)')
    _ensure_column(inspector, 'competition', 'registration_number', 'VARCHAR(100)')
    _ensure_column(inspector, 'competition', 'logo_path', 'VARCHAR(500)')
    _ensure_column(inspector, 'competition', 'disciplines', 'VARCHAR(255)')
    _ensure_column(inspector, 'event', 'category', 'VARCHAR(100)')
    _ensure_column(inspector, 'event', 'program_hours', 'VARCHAR(20)')
    _ensure_column(inspector, 'event', 'qualification_exam', 'VARCHAR(10)')
    _ensure_column(inspector, 'event', 'leader_full_name', 'VARCHAR(255)')
    _ensure_column(inspector, 'seminar_application_submission', 'origin', "VARCHAR(20) NOT NULL DEFAULT 'site'")
    _ensure_column(inspector, 'seminar_application_submission', 'updated_at', 'DATETIME')
    _ensure_nullable(inspector, 'seminar_application_submission', 'submitted_by_id')
    _ensure_column(inspector, 'document', 'section_id', 'INTEGER')
    _ensure_column(inspector, 'competition_application', 'logo_path', 'VARCHAR(500)')
    _ensure_column(inspector, 'competition_document', 'is_published', 'BOOLEAN NOT NULL DEFAULT 1')
    _ensure_column(inspector, 'regional_federation', 'intro_text', 'TEXT')
    _ensure_column(inspector, 'regional_federation', 'goals_text', 'TEXT')
    _ensure_column(inspector, 'regional_federation', 'contact_phone', 'VARCHAR(100)')
    _ensure_column(inspector, 'regional_federation', 'contact_email', 'VARCHAR(150)')
    _ensure_column(inspector, 'regional_federation', 'contact_address', 'VARCHAR(500)')
    _ensure_column(inspector, 'regional_federation', 'logo_white_path', 'VARCHAR(500)')
    _ensure_column(inspector, 'document_category', 'scope', "VARCHAR(30) NOT NULL DEFAULT 'цфо'")
    _ensure_column(inspector, 'regional_federation', 'subject_name', 'VARCHAR(255)')
    _ensure_column(inspector, 'athlete', 'is_active', 'BOOLEAN NOT NULL DEFAULT 1')


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


def seed_competition_document_taxonomy():
    """Начальное заполнение категорий бокового меню страницы «Нормативные
    документы» под Соревнования (scope='соревнования') — тот же приём,
    что seed_news_taxonomy: срабатывает только если таких категорий ещё
    нет, чтобы ручное удаление через админку не возвращалось обратно
    после перезапуска сервера."""
    if DocumentCategory.query.filter_by(scope='соревнования').count() == 0:
        for name in ('Законы', 'Минспорт России', 'WRF', 'ФРР'):
            db.session.add(DocumentCategory(name=name, scope='соревнования'))
        db.session.commit()


def seed_event_document_taxonomy():
    """Начальное заполнение категорий бокового меню страницы «Методические
    материалы» под Мероприятия (scope='мероприятия') — те же 4 пункта,
    что вторая строка меню на странице Мероприятия/Календарный план
    (routes/events.py: EVENT_TYPE_FILTERS), тот же приём, что
    seed_competition_document_taxonomy."""
    if DocumentCategory.query.filter_by(scope='мероприятия').count() == 0:
        for name in ('Спортивные судьи', 'Тренеры', 'Спортивная подготовка', 'Руководители организаций'):
            db.session.add(DocumentCategory(name=name, scope='мероприятия'))
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
