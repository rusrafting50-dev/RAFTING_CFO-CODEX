"""Главная страница, новости, контакты."""
from datetime import date, datetime

from flask import Blueprint, render_template, request
from sqlalchemy import extract

from models import Banner, Competition, Event, MediaAlbum, MediaVideo, News

bp = Blueprint('main', __name__)

NEWS_PER_PAGE = 5
# Меню фильтра на странице новостей — верхний уровень фильтрует по
# News.level; у пунктов с submenu ниже появляется вторая строка меню,
# фильтрующая дополнительно по News.category в рамках выбранного уровня.
NEWS_MENU = [
    {'value': '', 'label': 'Все', 'submenu': None},
    {
        'value': 'цфо',
        'label': 'ЦФО',
        'submenu': [
            ('Официально', 'Официально'),
            ('Соревнования', 'Соревнования'),
            ('Семинары', 'Семинары'),
            ('Люди и даты', 'Люди и даты'),
        ],
    },
    {
        'value': 'регион',
        'label': 'Регион',
        'submenu': [
            ('Официально', 'Официально'),
            ('Комитеты и комиссии', 'Комитеты и комиссии'),
            ('Соревнования', 'Соревнования'),
            ('Семинары', 'Семинары'),
            ('Люди и даты', 'Люди и даты'),
        ],
    },
    {'value': 'клуб', 'label': 'Клуб', 'submenu': None},
]
# Категория, из которой берутся новости в колонку "Официально". Значение
# совпадает с тем, что редактор реально выбирает в админке (сам текст
# пункта меню) — раньше здесь был отдельный "внутренний" код ('федерация'),
# не совпадающий ни с одним пунктом выпадающего списка категорий в форме
# новости, поэтому свежесозданные новости никогда не попадали в фильтр
# по второй строке меню.
OFFICIAL_NEWS_CATEGORY = 'официально'
# Выпадающие списки День/Месяц/Год над списком новостей — точные значения
# (а не относительный период "за сегодня/за месяц"), комбинируются между
# собой через И (например месяц=5 без года — все новости за май любого года).
NEWS_MONTHS = [
    (1, 'Январь'), (2, 'Февраль'), (3, 'Март'), (4, 'Апрель'),
    (5, 'Май'), (6, 'Июнь'), (7, 'Июль'), (8, 'Август'),
    (9, 'Сентябрь'), (10, 'Октябрь'), (11, 'Ноябрь'), (12, 'Декабрь'),
]
NEWS_MIN_YEAR = 2023
MEDIA_PER_PAGE = 8
MEDIA_MIN_YEAR = 2023


def news_menu_selection(item):
    """Подбирает под тегами конкретной новости пункт первой и второй
    строки меню — регистронезависимо, той же логикой, что и сам фильтр
    в news(), чтобы совпадало независимо от регистра значения в админке."""
    level_text = (item.level or '').strip().lower()
    active_entry = None
    for entry in NEWS_MENU:
        if entry['value'] and entry['value'].lower() == level_text:
            active_entry = entry
            break

    if not active_entry:
        return '', ''

    selected_category = ''
    if active_entry['submenu']:
        category_text = (item.category or '').strip().lower()
        for cat_value, _ in active_entry['submenu']:
            if cat_value.lower() == category_text:
                selected_category = cat_value
                break

    return active_entry['value'], selected_category


def official_news_list():
    return [
        item for item in News.query.filter_by(is_published=True)
        .order_by(News.published_at.desc())
        .all()
        if (item.category or '').lower() == OFFICIAL_NEWS_CATEGORY
    ][:20]


@bp.route('/')
def index():
    published_news = News.query.filter_by(is_published=True).order_by(News.published_at.desc())
    # Самая свежая новость идёт на баннер, а не в сетку карточек ниже —
    # там показываются следующие по свежести, без дублирования. Как
    # только выходит новая новость, баннерная автоматически "спускается"
    # в сетку — деление всегда идёт по первому/остальным элементам одной
    # и той же выборки, отдельного признака "уже показана" не нужно.
    hero_news = published_news.first()
    latest_news = published_news.offset(1).limit(4).all() if hero_news else []
    # Сначала ближайшие будущие (раньше — раньше в слайдере), а если их
    # меньше восьми — довобавляем прошедшие (сначала самые недавние),
    # чтобы слайдер не пустовал и показывал соревнования "задним числом".
    future_competitions = (
        Competition.query.filter(Competition.start_date >= date.today())
        .order_by(Competition.start_date.asc())
        .all()
    )
    past_competitions = (
        Competition.query.filter(Competition.start_date < date.today())
        .order_by(Competition.start_date.desc())
        .all()
    )
    upcoming_competitions = (future_competitions + past_competitions)[:8]
    upcoming_events = (
        Event.query.filter(Event.start_date >= date.today())
        .order_by(Event.start_date.asc())
        .limit(8)
        .all()
    )
    news_sidebar_banners = (
        Banner.query.filter_by(page='main.index', position='news_sidebar', is_active=True)
        .order_by(Banner.sort_order)
        .all()
    )
    latest_videos = (
        MediaVideo.query.filter_by(is_published=True)
        .order_by(MediaVideo.published_at.desc())
        .limit(2)
        .all()
    )
    latest_albums = (
        MediaAlbum.query.filter_by(is_published=True)
        .order_by(MediaAlbum.published_at.desc())
        .limit(2)
        .all()
    )
    return render_template(
        'main/index.html',
        hero_news=hero_news,
        latest_news=latest_news,
        upcoming_competitions=upcoming_competitions,
        upcoming_events=upcoming_events,
        news_sidebar_banners=news_sidebar_banners,
        latest_videos=latest_videos,
        latest_albums=latest_albums,
    )


@bp.route('/news')
def news():
    category = request.args.get('category', '')
    level = request.args.get('level', '')
    day = request.args.get('day', type=int)
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    search_query = request.args.get('q', '').strip()
    page = max(request.args.get('page', 1, type=int), 1)

    current_year = datetime.utcnow().year
    if day is not None and not (1 <= day <= 31):
        day = None
    if month is not None and not (1 <= month <= 12):
        month = None
    if year is not None and not (NEWS_MIN_YEAR <= year <= current_year):
        year = None

    query = News.query.filter_by(is_published=True)
    if day:
        query = query.filter(extract('day', News.published_at) == day)
    if month:
        query = query.filter(extract('month', News.published_at) == month)
    if year:
        query = query.filter(extract('year', News.published_at) == year)

    matching = query.order_by(News.published_at.desc()).all()

    # Регистронезависимо и в Python, а не через SQL func.lower(): SQLite
    # умеет сворачивать регистр только для ASCII, для кириллицы — нет
    # (та же причина, по которой поиск ниже тоже сделан в Python). Без
    # этого категория/уровень, введённые в админке с иной заглавной
    # буквой, чем в пункте меню, молча не находили ни одной новости.
    if category:
        needle = category.strip().lower()
        matching = [item for item in matching if (item.category or '').strip().lower() == needle]
    if level:
        needle = level.strip().lower()
        matching = [item for item in matching if (item.level or '').strip().lower() == needle]

    if search_query:
        # SQLite LIKE/ilike сворачивает регистр только для ASCII, не для
        # кириллицы — поиск по подстроке делаем в Python (str.lower()
        # работает корректно для любого языка), а не через SQL-фильтр.
        needle = search_query.lower()
        matching = [
            item for item in matching
            if needle in item.title.lower()
            or needle in (item.content or '').lower()
            or needle in (item.description or '').lower()
        ]

    total = len(matching)
    start = (page - 1) * NEWS_PER_PAGE
    news_items = matching[start:start + NEWS_PER_PAGE]
    has_next = start + NEWS_PER_PAGE < total

    official_news = official_news_list()

    return render_template(
        'main/news.html',
        news_items=news_items,
        official_news=official_news,
        news_menu=NEWS_MENU,
        news_months=NEWS_MONTHS,
        news_years=list(range(current_year, NEWS_MIN_YEAR - 1, -1)),
        news_days=list(range(1, 32)),
        selected_category=category,
        selected_level=level,
        selected_day=day,
        selected_month=month,
        selected_year=year,
        search_query=search_query,
        has_next=has_next,
        next_page=page + 1 if has_next else None,
    )


@bp.route('/media')
def media():
    media_type = request.args.get('type', 'photo')
    if media_type not in ('photo', 'video'):
        media_type = 'photo'
    day = request.args.get('day', type=int)
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    search_query = request.args.get('q', '').strip()
    page = max(request.args.get('page', 1, type=int), 1)

    current_year = datetime.utcnow().year
    if day is not None and not (1 <= day <= 31):
        day = None
    if month is not None and not (1 <= month <= 12):
        month = None
    if year is not None and not (MEDIA_MIN_YEAR <= year <= current_year):
        year = None

    model = MediaAlbum if media_type == 'photo' else MediaVideo
    query = model.query.filter_by(is_published=True)
    if day:
        query = query.filter(extract('day', model.published_at) == day)
    if month:
        query = query.filter(extract('month', model.published_at) == month)
    if year:
        query = query.filter(extract('year', model.published_at) == year)

    matching = query.order_by(model.published_at.desc()).all()

    if search_query:
        # См. news() выше — то же обоснование для поиска в Python.
        needle = search_query.lower()
        matching = [item for item in matching if needle in item.title.lower()]

    total = len(matching)
    start = (page - 1) * MEDIA_PER_PAGE
    media_items = matching[start:start + MEDIA_PER_PAGE]
    has_next = start + MEDIA_PER_PAGE < total

    return render_template(
        'main/media.html',
        media_type=media_type,
        media_items=media_items,
        media_months=NEWS_MONTHS,
        media_years=list(range(current_year, MEDIA_MIN_YEAR - 1, -1)),
        media_days=list(range(1, 32)),
        selected_day=day,
        selected_month=month,
        selected_year=year,
        search_query=search_query,
        has_next=has_next,
        next_page=page + 1 if has_next else None,
    )


@bp.route('/news/<int:news_id>')
def news_detail(news_id):
    item = News.query.filter_by(id=news_id, is_published=True).first_or_404()
    selected_level, selected_category = news_menu_selection(item)

    return render_template(
        'main/news_detail.html',
        item=item,
        official_news=official_news_list(),
        news_menu=NEWS_MENU,
        selected_category=selected_category,
        selected_level=selected_level,
        selected_day=None,
        selected_month=None,
        selected_year=None,
        search_query='',
        hide_search_row=True,
    )


@bp.route('/contacts')
def contacts():
    return render_template('main/contacts.html')
