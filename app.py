"""Точка входа Flask-приложения RAFTING_SITE."""
import os
import re
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, render_template, url_for

from auth import create_default_admin, ensure_schema, login_manager, seed_news_taxonomy
from models import PartnerLogo, db
from routes import register_blueprints

load_dotenv()

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


def event_status_label(value):
    """Статус мероприятия (анонс/идёт/завершён) -> подпись на сайте:
    "Прием заявок" / "Прием заявок окончен" / "Завершён"."""
    status_lower = (value or '').lower()
    if 'заверш' in status_lower:
        return 'Завершён'
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


def cap_first(value):
    """Первая буква прописная, остальной текст не трогаем (в отличие от
    str.capitalize(), который заодно понижает регистр всего остального —
    это ломало бы аббревиатуры вроде "ДК")."""
    text = str(value)
    if not text:
        return text
    return text[0].upper() + text[1:]


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
    app.jinja_env.filters['cap_first'] = cap_first
    app.jinja_env.filters['ru_plural'] = ru_plural
    app.jinja_env.filters['seminar_category_badge'] = seminar_category_badge
    app.jinja_env.filters['event_status_label'] = event_status_label
    app.jinja_env.filters['media_thumb'] = media_thumb
    app.jinja_env.filters['video_embed_url'] = video_embed_url
    app.jinja_env.tests['time_or_roman'] = is_time_or_roman

    register_blueprints(app)

    with app.app_context():
        db.create_all()
        ensure_schema()
        create_default_admin()
        seed_news_taxonomy()

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
