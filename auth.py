"""Авторизация: Flask-Login, хэширование паролей, первый admin при первом запуске."""
from werkzeug.security import generate_password_hash
from flask_login import LoginManager

from models import Document, DocumentCategory, DocumentSection, News, NewsCategory, NewsLevel, db, User

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


def _ensure_document_category_scoped_unique():
    """DocumentCategory.name раньше был уникален глобально (across всех
    scope сразу) — с добавлением категорий страницы федерации
    понадобилось, чтобы одно и то же название (например,
    «Основополагающие документы») могло независимо существовать в
    разных scope сразу (см. models.py: DocumentCategory). SQLite не
    поддерживает снятие/замену UNIQUE через ALTER TABLE — таблица
    пересоздаётся заново по текущей модели (уже с составным
    UNIQUE(name, scope) вместо старого UNIQUE(name)) с переносом всех
    данных, тем же приёмом, что _ensure_nullable."""
    from sqlalchemy import text

    table = 'document_category'
    with db.engine.connect() as conn:
        exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table"), {'table': table}
        ).fetchone()
        if not exists:
            return

        has_old_single_column_unique = False
        for _, index_name, is_unique, *_rest in conn.execute(text(f"PRAGMA index_list('{table}')")).fetchall():
            if not is_unique:
                continue
            columns = {
                row[2] for row in conn.execute(text(f"PRAGMA index_info('{index_name}')")).fetchall()
            }
            if columns == {'name'}:
                has_old_single_column_unique = True
                break

    if not has_old_single_column_unique:
        return

    with db.engine.begin() as conn:
        conn.execute(text('PRAGMA foreign_keys=OFF'))
        conn.execute(text(f'ALTER TABLE {table} RENAME TO {table}_old'))
        db.metadata.tables[table].create(bind=conn)
        conn.execute(text(
            f'INSERT INTO {table} (id, name, scope) SELECT id, name, scope FROM {table}_old'
        ))
        conn.execute(text(f'DROP TABLE {table}_old'))
        conn.execute(text('PRAGMA foreign_keys=ON'))
    print(f'[auth] Таблица {table}: UNIQUE(name) заменён на UNIQUE(name, scope).')


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
    _ensure_column(inspector, 'referee', 'is_active', 'BOOLEAN NOT NULL DEFAULT 1')
    _ensure_column(inspector, 'referee', 'municipality', 'VARCHAR(150)')
    _ensure_column(inspector, 'referee', 'specialization', 'VARCHAR(300)')
    _ensure_column(inspector, 'document', 'region_id', 'INTEGER')
    _ensure_document_category_scoped_unique()
    _ensure_column(inspector, 'document_section', 'sort_order', 'INTEGER NOT NULL DEFAULT 0')
    _ensure_column(inspector, 'document_category', 'sort_order', 'INTEGER NOT NULL DEFAULT 0')
    _ensure_column(inspector, 'document', 'link_url', 'VARCHAR(1000)')
    _ensure_column(inspector, 'athlete', 'photo_path', 'VARCHAR(500)')
    _ensure_column(inspector, 'competition', 'logo_is_manual', 'BOOLEAN NOT NULL DEFAULT 0')


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
        for name in ('Официально', 'Соревнования', 'Мероприятия', 'Люди и даты'):
            db.session.add(NewsCategory(name=name))

    if NewsLevel.query.count() == 0:
        for name in ('цфо', 'регион', 'отделение', 'клуб'):
            db.session.add(NewsLevel(name=name))

    db.session.commit()


def rename_seminar_news_category():
    """Разовое переименование категории новостей «Семинары» в
    «Мероприятия» — вторую строку меню фильтра новостей (routes/main.py:
    NEWS_MENU) сделали одинаковой у ЦФО и Региона под этим новым именем,
    а «Комитеты и комиссии» (была только у Региона) убрали из меню
    совсем. Переименовывает и уже опубликованные новости (News.category
    хранит название строкой, а не ссылкой — при переименовании
    NewsCategory он сам не меняется), чтобы они остались доступны через
    переименованный пункт меню. «Комитеты и комиссии» не трогает —
    удаление/переименование категории безопасно для существующих
    новостей (см. NewsCategory), но никакой готовой замены для нового
    пункта меню для них нет, отвязывать от категории вручную не наше
    решение."""
    category = NewsCategory.query.filter_by(name='Семинары').first()
    if not category:
        return
    if NewsCategory.query.filter_by(name='Мероприятия').first():
        return
    # LOWER() в SQLite не сворачивает регистр кириллицы — сравнение
    # делается в Python, та же причина, что у фильтра новостей в
    # routes/main.py: news().
    for item in News.query.all():
        if (item.category or '').strip().lower() == 'семинары':
            item.category = 'Мероприятия'
    category.name = 'Мероприятия'
    db.session.commit()


# Категории и их разделы бокового меню страницы «Нормативные документы»
# под Соревнования (scope='соревнования') — заданы федерацией; список
# без разделов (пустой список) означает категорию без вложенных
# разделов ("Все" в самом низу меню — не категория, а отдельная
# постоянная ссылка, см. competitions/documents.html).
COMPETITION_DOCUMENT_TAXONOMY = [
    ('Основополагающие документы', [
        'Уставные документы', 'Программы', 'Членство в ФРР', 'Государственная аккредитация',
    ]),
    ('Регламентирующие документы ФРР', []),
    ('Лицензирование и сертификация', [
        'Публичная финансовая информация', 'Лицензирование спортивных рафтинг клубов',
        'Нормативные документы по спортивным сооружениям',
        'Нормативные документы по оборудованию и снаряжению для рафтинга',
    ]),
    ('Нормативные документы', [
        'Правила вида спорта «рафтинг»', 'Единая всероссийская спортивная классификация',
        'Спортивные судьи', 'Спортивная подготовка', 'Иное',
    ]),
    ('Положение о соревнованиях', []),
    ('Методические материалы', []),
    ('Календарный план', []),
    ('Документы WRF', []),
]

# Прежнее название категории «Положение о соревнованиях» — нужно только
# rename_competition_regulations_category(), чтобы разово переименовать
# уже существующую категорию (и документы под ней) на уже работающих
# сайтах, а не только в новых, которые ещё ни разу не сидировались.
_OLD_COMPETITION_REGULATIONS_NAME = 'Положение о межрегиональных и всероссийских спортивных соревнованиях по виду спорта «рафтинг»'


def rename_competition_regulations_category():
    """Разовое переименование категории «Положение о межрегиональных и
    всероссийских спортивных соревнованиях по виду спорта «рафтинг»»
    (scope='соревнования') в короткое «Положение о соревнованиях» — на
    неё теперь ведёт отдельная ссылка во второй строке меню страницы
    «Спортивные соревнования» (competitions/calendar.html). Переносит и
    уже загруженные документы (Document.doc_category хранит название
    категории строкой, а не ссылкой — при переименовании категории он
    сам не меняется). Не трогает ничего, если категория уже
    переименована (обычный случай при повторных запусках) или названа
    по-другому вручную."""
    category = DocumentCategory.query.filter_by(
        scope='соревнования', name=_OLD_COMPETITION_REGULATIONS_NAME,
    ).first()
    if not category:
        return
    if DocumentCategory.query.filter_by(scope='соревнования', name='Положение о соревнованиях').first():
        return
    Document.query.filter_by(doc_category=_OLD_COMPETITION_REGULATIONS_NAME).update(
        {'doc_category': 'Положение о соревнованиях'}
    )
    category.name = 'Положение о соревнованиях'
    db.session.commit()


def ensure_competition_document_taxonomy():
    """Гарантирует, что все категории и разделы из COMPETITION_DOCUMENT_TAXONOMY
    существуют (scope='соревнования') — добавляет недостающие по
    названию, ничего не удаляет и не трогает уже существующие категории
    и разделы (в том числе случайно оставшиеся от более раннего
    дефолтного набора «Законы»/«Минспорт России»/«WRF»/«ФРР» — админ
    может убрать лишнее вручную через панель управления). Новым
    категориям/разделам sort_order проставляется по их позиции в
    COMPETITION_DOCUMENT_TAXONOMY — порядок в меню, пока админ не
    поменяет его сам кнопками ▲/▼ в панели управления.

    Раньше вместо этого была одноразовая migrate_competition_document_taxonomy(),
    срабатывавшая только при точном совпадении с исходным дефолтным
    набором — на части уже работающих сайтов список категорий к этому
    моменту успел разойтись (например, вручную удалили часть пунктов),
    из-за чего миграция молча пропускалась и новые категории так и не
    появлялись. Эта функция устроена проще и идемпотентна — можно
    спокойно вызывать при каждом старте сервера, а не один раз."""
    existing_categories = {
        category.name: category
        for category in DocumentCategory.query.filter_by(scope='соревнования').all()
    }
    changed = False
    for category_order, (name, section_names) in enumerate(COMPETITION_DOCUMENT_TAXONOMY):
        category = existing_categories.get(name)
        if not category:
            category = DocumentCategory(name=name, scope='соревнования', sort_order=category_order)
            db.session.add(category)
            db.session.flush()
            changed = True
        existing_section_names = {section.name for section in category.sections}
        for section_order, section_name in enumerate(section_names):
            if section_name not in existing_section_names:
                db.session.add(DocumentSection(category_id=category.id, name=section_name, sort_order=section_order))
                changed = True
    if changed:
        db.session.commit()


def seed_event_document_taxonomy():
    """Начальное заполнение категорий бокового меню страницы «Методические
    материалы» под Мероприятия (scope='мероприятия') — те же 4 пункта,
    что вторая строка меню на странице Мероприятия/Календарный план
    (routes/events.py: EVENT_TYPE_FILTERS), тот же приём, что
    seed_competition_document_taxonomy."""
    if DocumentCategory.query.filter_by(scope='мероприятия').count() == 0:
        for order, name in enumerate(('Спортивные судьи', 'Тренеры', 'Спортивная подготовка', 'Руководители организаций')):
            db.session.add(DocumentCategory(name=name, scope='мероприятия', sort_order=order))
        db.session.commit()


def seed_equipment_document_taxonomy():
    """Начальное заполнение категорий страницы «Оборудование и снаряжение»
    под Соревнования — отдельно для двух аудиторий (первая строка меню
    на самой странице, routes/competitions.py: EQUIPMENT_AUDIENCES), тот
    же приём, что seed_competition_document_taxonomy."""
    if DocumentCategory.query.filter_by(scope='оборудование_спортсмены').count() == 0:
        for order, name in enumerate((
            'Рафты для спорта', 'Вёсла для спорта', 'Каски', 'Страховочные жилеты',
            'Одежда слой из неопрена', 'Одежда верхний слой',
        )):
            db.session.add(DocumentCategory(name=name, scope='оборудование_спортсмены', sort_order=order))
        db.session.commit()
    if DocumentCategory.query.filter_by(scope='оборудование_организаторы').count() == 0:
        for order, name in enumerate((
            'Старт-Финиш', 'Дистанция «Слалом»', 'Дистанция «Параллельный спринт»',
            'Программное обеспечение для секретариата',
        )):
            db.session.add(DocumentCategory(name=name, scope='оборудование_организаторы', sort_order=order))
        db.session.commit()


# Категории и их разделы бокового меню страницы конкретной региональной
# федерации (scope='федерация') — общий для всех федераций список
# категорий/разделов (см. routes/regions.py: FEDERATION_SIDEBAR_LAYOUT),
# а сами загруженные документы у каждой федерации свои (Document.region_id).
FEDERATION_DOCUMENT_TAXONOMY = [
    ('Основополагающие документы', [
        'Уставные документы', 'Программы', 'Членство в ФРР', 'Государственная аккредитация',
    ]),
    ('Структура Федерации', [
        'Положение о структуре Федерации', 'Местные отделения Федерации',
        'Коллегия судей', 'Тренерский совет', 'Совет клубов',
    ]),
    ('Лицензирование и сертификация', []),
    ('Положение о межмуниципальных и региональных спортивных соревнованиях по виду спорта «рафтинг»', []),
]


def seed_federation_document_taxonomy():
    """Начальное заполнение категорий и разделов бокового меню страницы
    конкретной федерации (scope='федерация') — тот же приём, что
    seed_competition_document_taxonomy. Разделы получают sort_order по
    своей позиции в FEDERATION_DOCUMENT_TAXONOMY — порядок в меню задан
    федерацией, а не алфавитный."""
    if DocumentCategory.query.filter_by(scope='федерация').count() == 0:
        for category_order, (name, section_names) in enumerate(FEDERATION_DOCUMENT_TAXONOMY):
            category = DocumentCategory(name=name, scope='федерация', sort_order=category_order)
            db.session.add(category)
            db.session.flush()
            for section_order, section_name in enumerate(section_names):
                db.session.add(DocumentSection(category_id=category.id, name=section_name, sort_order=section_order))
        db.session.commit()


def restore_federation_goals_section():
    """Разовая миграция: пункт бокового меню «О федерации» «Направления
    деятельности» возвращается к тому, чем он был до категории документов
    из FEDERATION_DOCUMENT_TAXONOMY (см. routes/regions.py:
    FUNCTIONAL_SECTIONS/FEDERATION_SIDEBAR_LAYOUT) — свободный текст
    (RegionalFederation.goals_text, поле «Направления деятельности» в
    админке), как раньше был раздел «Цели и задачи».

    Категория DocumentCategory «Направления деятельности»
    (scope='федерация'), которую сеяла seed_federation_document_taxonomy
    до этой миграции, удаляется — но только если у неё, как и было
    изначально, нет разделов: если админ вручную добавил в неё разделы,
    это уже не тот дефолтный пустой пункт, трогать его не нужно.
    Документы, если они успели куда-то загрузиться под этой категорией
    (Document.doc_category хранится строкой, а не ссылкой), никуда не
    делись — сама категория удаляется, а не они, документы останутся
    видны в списке «Все» на странице федерации."""
    category = DocumentCategory.query.filter_by(name='Направления деятельности', scope='федерация').first()
    if not category or category.sections:
        return
    db.session.delete(category)
    db.session.commit()


def _apply_initial_order(rows, name_order):
    """rows — список ORM-объектов с полями sort_order/name одной группы
    (все категории одного scope, либо все разделы одной категории).
    Проставляет sort_order по позиции названия в name_order, но только
    если у ВСЕХ rows сейчас одинаковый sort_order — то есть порядок
    среди них ещё никто и никак не задавал (ни при сидировании новых
    категорий/разделов — см. ensure_competition_document_taxonomy и
    seed_federation_document_taxonomy, ни вручную кнопками ▲/▼ в панели
    управления). Как только у любого элемента группы значение
    отличается — группу больше не трогает, чтобы не затереть ручную
    перестановку. Возвращает True, если что-то изменила."""
    if len({row.sort_order for row in rows}) > 1:
        return False
    position = {name: index for index, name in enumerate(name_order)}
    changed = False
    for row in rows:
        order = position.get(row.name)
        if order is not None and row.sort_order != order:
            row.sort_order = order
            changed = True
    return changed


def fix_legacy_document_taxonomy_order():
    """Одноразовая по сути простановка sort_order категориям и разделам,
    созданным до появления этого поля (стоит сплошной дефолт 0, то есть
    сортировка сейчас алфавитная) — приводит их к порядку, заданному в
    COMPETITION_DOCUMENT_TAXONOMY/FEDERATION_DOCUMENT_TAXONOMY. См.
    _apply_initial_order — как только порядок где-то уже задан (при
    сидировании новых категорий или вручную через панель управления),
    эта функция такую группу больше не трогает, поэтому её можно
    спокойно вызывать при каждом старте сервера."""
    changed = False

    competition_categories = DocumentCategory.query.filter_by(scope='соревнования').all()
    changed |= _apply_initial_order(competition_categories, [name for name, _ in COMPETITION_DOCUMENT_TAXONOMY])
    for name, section_names in COMPETITION_DOCUMENT_TAXONOMY:
        category = next((c for c in competition_categories if c.name == name), None)
        if category:
            changed |= _apply_initial_order(category.sections, section_names)

    federation_categories = DocumentCategory.query.filter_by(scope='федерация').all()
    changed |= _apply_initial_order(federation_categories, [name for name, _ in FEDERATION_DOCUMENT_TAXONOMY])
    for name, section_names in FEDERATION_DOCUMENT_TAXONOMY:
        category = next((c for c in federation_categories if c.name == name), None)
        if category:
            changed |= _apply_initial_order(category.sections, section_names)

    if changed:
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
