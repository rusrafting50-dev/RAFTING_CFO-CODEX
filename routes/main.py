"""Главная страница, новости, контакты."""
from datetime import date, datetime

from flask import Blueprint, render_template, request
from sqlalchemy import extract

from models import Competition, Event, News

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
            ('федерация', 'Официально'),
            ('соревнование', 'Соревнования'),
            ('мероприятие', 'Семинары'),
            ('люди_и_даты', 'Люди и даты'),
        ],
    },
    {
        'value': 'регион',
        'label': 'Регион',
        'submenu': [
            ('федерация', 'Официально'),
            ('комитеты_и_комиссии', 'Комитеты и комиссии'),
            ('соревнование', 'Соревнования'),
            ('мероприятие', 'Семинары'),
            ('люди_и_даты', 'Люди и даты'),
        ],
    },
    {'value': 'клуб', 'label': 'Клуб', 'submenu': None},
]
# Категория, из которой берутся новости в колонку "Официально".
OFFICIAL_NEWS_CATEGORY = 'федерация'
# Выпадающие списки День/Месяц/Год над списком новостей — точные значения
# (а не относительный период "за сегодня/за месяц"), комбинируются между
# собой через И (например месяц=5 без года — все новости за май любого года).
NEWS_MONTHS = [
    (1, 'Январь'), (2, 'Февраль'), (3, 'Март'), (4, 'Апрель'),
    (5, 'Май'), (6, 'Июнь'), (7, 'Июль'), (8, 'Август'),
    (9, 'Сентябрь'), (10, 'Октябрь'), (11, 'Ноябрь'), (12, 'Декабрь'),
]
NEWS_MIN_YEAR = 2023


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
    upcoming_competitions = (
        Competition.query.filter(Competition.start_date >= date.today())
        .order_by(Competition.start_date.asc())
        .limit(8)
        .all()
    )
    upcoming_events = (
        Event.query.filter(Event.start_date >= date.today())
        .order_by(Event.start_date.asc())
        .limit(8)
        .all()
    )
    return render_template(
        'main/index.html',
        hero_news=hero_news,
        latest_news=latest_news,
        upcoming_competitions=upcoming_competitions,
        upcoming_events=upcoming_events,
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
        needle = category.lower()
        matching = [item for item in matching if (item.category or '').lower() == needle]
    if level:
        needle = level.lower()
        matching = [item for item in matching if (item.level or '').lower() == needle]

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

    official_news = [
        item for item in News.query.filter_by(is_published=True)
        .order_by(News.published_at.desc())
        .all()
        if (item.category or '').lower() == OFFICIAL_NEWS_CATEGORY
    ][:20]

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


@bp.route('/contacts')
def contacts():
    return render_template('main/contacts.html')
