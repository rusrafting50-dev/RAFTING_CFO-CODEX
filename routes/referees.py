"""Судьи всероссийской категории."""
from flask import Blueprint, render_template, request

from models import Referee

bp = Blueprint('referees', __name__)


@bp.route('/')
def index():
    category = request.args.get('category', '')
    territory = request.args.get('territory', '')

    query = Referee.query
    if category:
        query = query.filter_by(category=category)
    if territory:
        query = query.filter_by(territory=territory)

    referees = query.order_by(Referee.full_name.asc()).all()

    categories = [
        row[0] for row in
        Referee.query.with_entities(Referee.category).filter(Referee.category.isnot(None)).distinct()
    ]
    territories = [
        row[0] for row in
        Referee.query.with_entities(Referee.territory).filter(Referee.territory.isnot(None)).distinct()
    ]

    return render_template(
        'referees/list.html',
        referees=referees,
        categories=categories,
        territories=territories,
        selected_category=category,
        selected_territory=territory,
    )
