"""Главная страница, новости, контакты."""
from datetime import date, datetime

from flask import Blueprint, render_template, request

from models import Competition, Event, News

bp = Blueprint('main', __name__)

NEWS_PER_PAGE = 5
# Пункты меню фильтра на странице новостей: (значение News.category, подпись).
NEWS_MENU = [
    ('', 'Все'),
    ('соревнование', 'Соревнования'),
    ('регион', 'Регионы'),
    ('мероприятие', 'Мероприятия'),
]
# Категория, из которой берутся новости в колонку "Официально".
OFFICIAL_NEWS_CATEGORY = 'федерация'
# Быстрые фильтры по периоду публикации над списком новостей.
NEWS_PERIODS = [
    ('', 'За все время'),
    ('day', 'День'),
    ('month', 'Месяц'),
    ('year', 'Год'),
]


def _period_start(period):
    """Начало текущего периода (день/месяц/год) для фильтра публикаций."""
    now = datetime.utcnow()
    if period == 'day':
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == 'month':
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period == 'year':
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return None


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
    period = request.args.get('period', '')
    search_query = request.args.get('q', '').strip()
    page = max(request.args.get('page', 1, type=int), 1)

    if period not in dict(NEWS_PERIODS):
        period = ''

    query = News.query.filter_by(is_published=True)
    if category:
        query = query.filter_by(category=category)
    period_start = _period_start(period)
    if period_start:
        query = query.filter(News.published_at >= period_start)

    matching = query.order_by(News.published_at.desc()).all()

    if search_query:
        # SQLite LIKE/ilike сворачивает регистр только для ASCII, не для
        # кириллицы — поиск по подстроке делаем в Python (str.lower()
        # работает корректно для любого языка), а не через SQL-фильтр.
        needle = search_query.lower()
        matching = [
            item for item in matching
            if needle in item.title.lower() or needle in (item.content or '').lower()
        ]

    total = len(matching)
    start = (page - 1) * NEWS_PER_PAGE
    news_items = matching[start:start + NEWS_PER_PAGE]
    has_next = start + NEWS_PER_PAGE < total

    official_news = (
        News.query.filter_by(is_published=True, category=OFFICIAL_NEWS_CATEGORY)
        .order_by(News.published_at.desc())
        .limit(20)
        .all()
    )

    return render_template(
        'main/news.html',
        news_items=news_items,
        official_news=official_news,
        news_menu=NEWS_MENU,
        news_periods=NEWS_PERIODS,
        selected_category=category,
        selected_period=period,
        search_query=search_query,
        has_next=has_next,
        next_page=page + 1 if has_next else None,
    )


@bp.route('/contacts')
def contacts():
    return render_template('main/contacts.html')
