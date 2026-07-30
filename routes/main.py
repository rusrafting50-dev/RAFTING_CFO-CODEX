"""Главная страница, новости, контакты."""
from datetime import date

from flask import Blueprint, render_template, request

from models import Competition, News

bp = Blueprint('main', __name__)

NEWS_PER_PAGE = 9


@bp.route('/')
def index():
    latest_news = (
        News.query.filter_by(is_published=True)
        .order_by(News.published_at.desc())
        .limit(5)
        .all()
    )
    upcoming_competitions = (
        Competition.query.filter(Competition.start_date >= date.today())
        .order_by(Competition.start_date.asc())
        .limit(5)
        .all()
    )
    return render_template(
        'main/index.html',
        latest_news=latest_news,
        upcoming_competitions=upcoming_competitions,
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
