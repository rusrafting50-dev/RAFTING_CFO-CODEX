"""Точка входа Flask-приложения RAFTING_SITE."""
import os
import re
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, render_template, url_for
from markupsafe import Markup, escape

from auth import (
    add_federation_calendar_document_category, create_default_admin, ensure_competition_document_taxonomy,
    ensure_schema, fix_legacy_document_taxonomy_order, login_manager,
    remove_local_branches_document_section, rename_competition_regulations_category,
    rename_federation_regulations_category, rename_seminar_news_category,
    restore_federation_goals_section,
    seed_equipment_document_taxonomy, seed_event_document_taxonomy,
    seed_federation_document_taxonomy, seed_news_taxonomy,
)
from models import PartnerLogo, db
from routes import register_blueprints

# override=True — .env должен побеждать даже если такая переменная уже
# случайно задана на уровне Windows (иначе пустое/старое системное
# значение молча маскирует правильное значение из .env).
load_dotenv(override=True)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

_TIME_CELL_RE = re.compile(r'^\d+(:\d{2})+(\.\d+)?$')  # "1:35.50", "00:10", "20:00.00"
_ROMAN_CELL_RE = re.compile(r'^[IVXLCDM]+$')  # разряды ("I", "II", "III")

_YOUTUBE_EMBED_RE = re.compile(
    r'(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})'
)
_VK_VIDEO_RE = re.compile(r'vk(?:video)?\.(?:com|ru)/video(-?\d+)_(\d+)')


def video_embed_url(url):
    """Ссылка для встраивания видео в свой плеер (iframe) на сайте —
    YouTube и VK Видео; для остальных источников встраивание недоступно,
    пусто (шаблон в этом случае просто открывает исходную ссылку)."""
    if not url:
        return ''
    youtube_match = _YOUTUBE_EMBED_RE.search(url)
    if youtube_match:
        return f'https://www.youtube.com/embed/{youtube_match.group(1)}'
    vk_match = _VK_VIDEO_RE.search(url)
    if vk_match:
        owner_id, video_id = vk_match.groups()
        return f'https://vk.com/video_ext.php?oid={owner_id}&id={video_id}&hd=2'
    return ''


def is_time_or_roman(value):
    """Ячейки таблиц результатов со временем (М:СС.сс, ММ:СС) или
    разрядом в виде римских цифр (I/II/III) — их выравниваем по центру,
    как числа, хотя формально это строки."""
    text = str(value)
    return bool(_TIME_CELL_RE.match(text) or _ROMAN_CELL_RE.match(text))

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


def format_ru_date_range(start, end):
    """Диапазон дат без повторов месяца/года у обеих границ, если они
    совпадают: "23 – 24 мая 2026" (тот же месяц и год), "31 мая –
    1 июня 2026" (тот же год, месяц разный), иначе — обе даты
    полностью ("30 декабря 2026 – 2 января 2027")."""
    if not start:
        return ''
    if not end or end == start:
        return format_ru_date_full(start)
    if start.year == end.year:
        if start.month == end.month:
            return f'{start.day} – {end.day} {RU_MONTHS_GENITIVE[start.month]} {start.year}'
        return (f'{start.day} {RU_MONTHS_GENITIVE[start.month]} – '
                f'{end.day} {RU_MONTHS_GENITIVE[end.month]} {start.year}')
    return f'{format_ru_date_full(start)} – {format_ru_date_full(end)}'


def format_numeric_date_range(start, end):
    """Диапазон дат цифрами — таблица заявок на включение в ЕКП
    (competitions/calendar.html, столбец «Сроки проведения») и карточки
    соревнований на главной странице (main/index.html): "23 -
    24.05.2026" (тот же месяц и год — начало без месяца/года), "23.05 -
    24.06.2026" (тот же год, месяц разный — начало с месяцем без года),
    иначе — обе даты полностью ("30.12.2026 - 02.01.2027"). День и
    месяц всегда двумя цифрами."""
    if not start:
        return ''
    if not end or end == start:
        return f'{start.day:02d}.{start.month:02d}.{start.year}'
    if start.year == end.year:
        if start.month == end.month:
            return f'{start.day:02d} - {end.day:02d}.{end.month:02d}.{end.year}'
        return f'{start.day:02d}.{start.month:02d} - {end.day:02d}.{end.month:02d}.{end.year}'
    return f'{start.day:02d}.{start.month:02d}.{start.year} - {end.day:02d}.{end.month:02d}.{end.year}'


def event_status_label(value, applications_deadline=None):
    """Статус мероприятия (анонс/идёт/завершён) -> подпись на сайте:
    "Прием заявок" / "Прием заявок окончен" / "Прием заявок завершён".

    applications_deadline — «До даты» из блока «Положение о семинаре» в
    SPORTS_REFEREE (Event.applications_deadline), отдельный от start_date/
    end_date самого семинара срок (обычно раньше них). Как только он
    проходит, статус переключается на «Прием заявок завершён» независимо
    от анонс/идёт/завершён — иначе семинар с уже прошедшим сроком подачи
    заявок, но ещё не начавшийся (status='анонс'), продолжал бы
    показывать «Прием заявок», как будто заявку ещё можно подать."""
    if applications_deadline and datetime.utcnow().date() > applications_deadline:
        return 'Прием заявок завершён'
    status_lower = (value or '').lower()
    if 'заверш' in status_lower:
        return 'Прием заявок завершён'
    if status_lower == 'идёт':
        return 'Прием заявок окончен'
    if status_lower == 'анонс':
        return 'Прием заявок'
    return cap_first(value)


_SEMINAR_CATEGORY_BADGE = {
    'Всероссийская': 'bg-danger',
    'Первая': 'bg-warning text-dark',
    'Вторая': 'bg-info text-dark',
    'Третья': 'bg-secondary',
    'Юный судья': 'bg-success',
}


def seminar_category_badge(value):
    """Категория семинара -> класс цветного бейджа Bootstrap — те же
    цвета, что и на карточке семинара в SPORTS_REFEREE."""
    return _SEMINAR_CATEGORY_BADGE.get(value, 'bg-secondary')


def ru_plural(count, one, few, many):
    """Русское склонение по числу (1 участник / 2 участника / 5 участников)."""
    count = abs(int(count))
    if count % 10 == 1 and count % 100 != 11:
        return one
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return few
    return many


def file_extension(path):
    """Расширение файла в нижнем регистре без точки ("pdf", "docx") —
    для выбора значка типа файла на странице документов."""
    if not path or '.' not in path:
        return ''
    return path.rsplit('.', 1)[1].lower()


_DOCUMENT_EXTENSION_ICONS = {
    'pdf': 'pdf_icon_48.png',
    'doc': 'word_icon_48.png',
    'docx': 'word_icon_48.png',
    'xls': 'excel_icon_48.png',
    'xlsx': 'excel_icon_48.png',
}


def document_icon(document):
    """Значок карточки документа на страницах со списком документов —
    по расширению файла (см. _DOCUMENT_EXTENSION_ICONS), а для документа
    со ссылкой вместо файла (Document.link_url, панель управления) —
    всегда link_icon_48.png, независимо от того, что за страница на том
    конце ссылки. None — нет иконки под расширение, значит в шаблоне
    используется общая заглушка."""
    if document.link_url:
        return 'link_icon_48.png'
    return _DOCUMENT_EXTENSION_ICONS.get(file_extension(document.file_path))


def document_href(document, external=False):
    """Куда ведёт открытие/скачивание документа — внешняя ссылка как
    есть (Document.link_url), либо обычный путь до файла в static/uploads."""
    if document.link_url:
        return document.link_url
    return url_for('static', filename=document.file_path, _external=external)


def cap_first(value):
    """Первая буква прописная, остальной текст не трогаем (в отличие от
    str.capitalize(), который заодно понижает регистр всего остального —
    это ломало бы аббревиатуры вроде "ДК")."""
    text = str(value)
    if not text:
        return text
    return text[0].upper() + text[1:]


_RICHTEXT_TAG_RE = re.compile(r'<[a-zA-Zа-яА-Я][^>]*>')


def richtext_filter(value):
    """Поля вроде RegionalFederation.intro_text/goals_text, Club.*_text,
    News.content — раньше обычный текст (выводился экранированным, переносы
    строк — через CSS white-space: pre-line у .fed-intro/.news-detail-content).
    С добавлением редактора форматированного текста в панели управления
    (static/js/main.js: initRichTextEditors) новые значения — уже HTML,
    очищенный на сервере при сохранении (routes/admin.py через
    richtext.sanitize_rich_text) — его можно выводить как есть, без
    экранирования. Значение, сохранённое до этого изменения, тегов не
    содержит — считаем его таким при отсутствии похожего на тег фрагмента
    (не просто «есть ли в тексте символ <», чтобы не принять за HTML
    случайное «x < 5» в старом тексте) и экранируем как раньше."""
    if not value:
        return ''
    if _RICHTEXT_TAG_RE.search(value):
        return Markup(value)
    return Markup(escape(value))


def media_thumb(path):
    """Путь к превью видео/фото: обычно локальный файл в static/uploads
    (резолвится как обычно), но для видео с YouTube-обложкой (см.
    admin.media_video_new/_edit) это готовая внешняя ссылка на img.youtube.com —
    её нужно вывести как есть, без url_for('static', ...)."""
    if not path:
        return ''
    if path.startswith('http://') or path.startswith('https://'):
        # Записи, сохранённые до перехода на mqdefault.jpg (см.
        # admin.youtube_thumbnail_url), ещё указывают на hqdefault.jpg —
        # у него канва 4:3 с чёрными полосами для 16:9 видео. Правим на
        # лету при выводе, без миграции базы.
        if path.startswith('https://img.youtube.com/vi/') and path.endswith('/hqdefault.jpg'):
            return path[: -len('hqdefault.jpg')] + 'mqdefault.jpg'
        return path
    return url_for('static', filename=path)


def asset_url(filename):
    """Ссылка на static/ с ?v=<время изменения файла> — правки CSS/JS
    иначе не долетают до браузера, пока пользователь не сбросит кэш
    вручную (URL файла не меняется, значит браузер годами отдаёт из
    кэша старую версию)."""
    path = os.path.join(BASE_DIR, 'static', filename)
    try:
        version = int(os.path.getmtime(path))
    except OSError:
        version = 0
    return f"{url_for('static', filename=filename)}?v={version}"


_STATIC_IMAGE_SIZE_CACHE = {}


def static_image_size(filename):
    """Реальные (width, height) файла в static/ — выводятся как атрибуты
    width/height у логотипа в шапке (base.html), чтобы браузер знал его
    пропорции ДО того, как файл реально загрузится. Без этого <img> без
    width/height до загрузки имеет нулевой размер, а main.js, меряющий
    положение логотипа для расстановки пунктов меню, в этот момент
    получает неверные (нулевые) координаты — пункты меню на долю секунды
    оказывались не на своём месте и заметно "доезжали" туда чуть позже.
    Кэшируется в памяти по (файл, время изменения) — файл логотипа не
    меняется между запросами, декодировать его на каждый рендер шапки незачем."""
    path = os.path.join(BASE_DIR, 'static', filename)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None

    cached = _STATIC_IMAGE_SIZE_CACHE.get(filename)
    if cached and cached[0] == mtime:
        return cached[1]

    try:
        from PIL import Image
        with Image.open(path) as img:
            size = img.size
    except Exception:
        return None

    _STATIC_IMAGE_SIZE_CACHE[filename] = (mtime, size)
    return size


_STATIC_IMAGE_TRANSPARENCY_CACHE = {}


def static_image_has_transparency(filename):
    """Есть ли у файла реально прозрачные пиксели — не просто режим с
    альфа-каналом (PNG часто хранит его даже у полностью непрозрачных
    картинок), а хотя бы один пиксель с альфой меньше 255. Нужно карточке
    соревнования (competitions/calendar.html) — логотип с прозрачным фоном
    на тёмном градиенте .comp-card-photo просвечивает тёмным, вместо
    градиента в этом случае показывается белый фон. Кэш по (файл, mtime) —
    тот же приём, что static_image_size."""
    if not filename:
        return False
    path = os.path.join(BASE_DIR, 'static', filename)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return False

    cached = _STATIC_IMAGE_TRANSPARENCY_CACHE.get(filename)
    if cached and cached[0] == mtime:
        return cached[1]

    try:
        from PIL import Image
        with Image.open(path) as img:
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                has_alpha = img.convert('RGBA').getchannel('A').getextrema()[0] < 255
            else:
                has_alpha = False
    except Exception:
        has_alpha = False

    _STATIC_IMAGE_TRANSPARENCY_CACHE[filename] = (mtime, has_alpha)
    return has_alpha


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
    app.jinja_env.filters['ru_date_range'] = format_ru_date_range
    app.jinja_env.filters['numeric_date_range'] = format_numeric_date_range
    app.jinja_env.filters['cap_first'] = cap_first
    app.jinja_env.filters['ru_plural'] = ru_plural
    app.jinja_env.filters['file_extension'] = file_extension
    app.jinja_env.filters['document_icon'] = document_icon
    app.jinja_env.filters['document_href'] = document_href
    app.jinja_env.filters['seminar_category_badge'] = seminar_category_badge
    app.jinja_env.filters['event_status_label'] = event_status_label
    app.jinja_env.filters['media_thumb'] = media_thumb
    app.jinja_env.filters['richtext'] = richtext_filter
    app.jinja_env.filters['video_embed_url'] = video_embed_url
    app.jinja_env.tests['time_or_roman'] = is_time_or_roman
    app.jinja_env.globals['asset_url'] = asset_url
    app.jinja_env.globals['static_image_size'] = static_image_size
    app.jinja_env.globals['static_image_has_transparency'] = static_image_has_transparency

    register_blueprints(app)

    with app.app_context():
        db.create_all()
        ensure_schema()
        create_default_admin()
        seed_news_taxonomy()
        rename_seminar_news_category()
        rename_competition_regulations_category()
        ensure_competition_document_taxonomy()
        seed_event_document_taxonomy()
        seed_equipment_document_taxonomy()
        seed_federation_document_taxonomy()
        add_federation_calendar_document_category()
        rename_federation_regulations_category()
        restore_federation_goals_section()
        remove_local_branches_document_section()
        fix_legacy_document_taxonomy_order()

    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}

    @app.context_processor
    def inject_partner_logos():
        # Полоса логотипов перед подвалом (base.html) видна на каждой
        # странице сайта — данные для неё подтягиваются здесь, а не в
        # каждом view отдельно.
        logos = PartnerLogo.query.filter_by(is_active=True).order_by(PartnerLogo.sort_order).all()
        return {'partner_logos': logos}

    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5003)
