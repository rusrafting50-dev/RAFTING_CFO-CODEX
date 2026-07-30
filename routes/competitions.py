"""Соревнования: календарный план, текущие, архив, страница соревнования."""
from datetime import date

from flask import Blueprint, render_template, request
from sqlalchemy import extract

from models import Competition, CompetitionDocument

bp = Blueprint('competitions', __name__)


@bp.route('/')
def calendar():
    """Календарный план текущего года."""
    year = request.args.get('year', date.today().year, type=int)

    competitions = (
        Competition.query.filter(extract('year', Competition.start_date) == year)
        .order_by(Competition.start_date.asc())
        .all()
    )

    return render_template('competitions/calendar.html', competitions=competitions, year=year)


@bp.route('/current')
def current():
    competitions = (
        Competition.query.filter(Competition.status == 'идёт')
        .order_by(Competition.start_date.asc())
        .all()
    )
    return render_template(
        'competitions/list.html',
        competitions=competitions,
        title='Текущие соревнования',
    )


@bp.route('/archive')
def archive():
    year = request.args.get('year', type=int)

    query = Competition.query.filter(
        (Competition.status == 'завершены') | (Competition.end_date < date.today())
    )
    if year:
        query = query.filter(extract('year', Competition.start_date) == year)

    competitions = query.order_by(Competition.start_date.desc()).all()

    years = sorted(
        {c.start_date.year for c in Competition.query.all() if c.start_date},
        reverse=True,
    )

    return render_template(
        'competitions/list.html',
        competitions=competitions,
        title='Архив соревнований',
        archive=True,
        years=years,
        selected_year=year,
    )


@bp.route('/<int:competition_id>')
def detail(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    documents = (
        CompetitionDocument.query.filter_by(competition_id=competition_id)
        .order_by(CompetitionDocument.doc_type)
        .all()
    )

    documents_by_type = {}
    for document in documents:
        documents_by_type.setdefault(document.doc_type, []).append(document)

    return render_template(
        'competitions/detail.html',
        competition=competition,
        documents_by_type=documents_by_type,
    )
