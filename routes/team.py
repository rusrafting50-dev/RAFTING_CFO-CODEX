"""Сборная команда: спортсмены и тренеры."""
from flask import Blueprint, render_template, request

from models import Athlete

bp = Blueprint('team', __name__)


@bp.route('/')
def index():
    role = request.args.get('role', '')
    discipline = request.args.get('discipline', '')
    territory = request.args.get('territory', '')

    query = Athlete.query
    if role:
        query = query.filter_by(role=role)
    if discipline:
        query = query.filter_by(discipline=discipline)
    if territory:
        query = query.filter_by(territory=territory)

    athletes = query.order_by(Athlete.full_name.asc()).all()

    disciplines = [
        row[0] for row in
        Athlete.query.with_entities(Athlete.discipline).filter(Athlete.discipline.isnot(None)).distinct()
    ]
    territories = [
        row[0] for row in
        Athlete.query.with_entities(Athlete.territory).filter(Athlete.territory.isnot(None)).distinct()
    ]

    return render_template(
        'team/list.html',
        athletes=athletes,
        disciplines=disciplines,
        territories=territories,
        selected_role=role,
        selected_discipline=discipline,
        selected_territory=territory,
    )
