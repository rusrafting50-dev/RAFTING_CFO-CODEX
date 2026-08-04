"""Главная страница, новости, контакты."""
from datetime import date

from flask import Blueprint, render_template, request

from models import Competition, Event, News

bp = Blueprint('main', __name__)

NEWS_PER_PAGE = 9


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
    page = request.args.get('page', 1, type=int)

    query = News.query.filter_by(is_published=True)
    if category:
        query = query.filter_by(category=category)

    pagination = query.order_by(News.published_at.desc()).paginate(
        page=page, per_page=NEWS_PER_PAGE, error_out=False
    )

    categories = [
        row[0] for row in
        News.query.with_entities(News.category).filter(News.category.isnot(None)).distinct()
    ]

    return render_template(
        'main/news.html',
        pagination=pagination,
        news_items=pagination.items,
        categories=categories,
        selected_category=category,
        breadcrumbs=[{'label': 'Новости'}],
    )


@bp.route('/contacts')
def contacts():
    return render_template('main/contacts.html', breadcrumbs=[{'label': 'Контакты'}])
