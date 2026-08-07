"""Соревнования: календарный план, текущие, архив, страница соревнования."""
import json
from datetime import date

from flask import Blueprint, render_template, request
from sqlalchemy import extract

from models import Competition, CompetitionDocument

bp = Blueprint('competitions', __name__)

# Порядок и подписи дисциплин на вкладке "Результаты" (второй ряд меню).
# Список фиксированный — пункт появляется, только если для него реально
# пришли данные от COREZ (многоборье пересчитывается инкрементально по мере
# синхронизации остальных дисциплин, поэтому его пункт появляется вместе
# со спринтом, а не только в конце соревнования).
RESULT_DISCIPLINES = [
    ('результаты_спринт', 'Спринт'),
    ('результаты_пс', 'Параллельный спринт'),
    ('результаты_слалом', 'Слалом'),
    ('результаты_дг', 'Длинная гонка'),
    ('результаты_мб', 'Многоборье'),
]


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

    result_doc_types = {doc_type for doc_type, _ in RESULT_DISCIPLINES}

    documents_by_type = {}
    results_by_type = {}
    for document in documents:
        if document.results_data:
            # Протокол пришёл от COREZ как структурированные данные — строим таблицу.
            # Столбцы — объединение ключей всех строк с сохранением порядка появления.
            rows = json.loads(document.results_data)
            columns = []
            for row in rows:
                for key in row.keys():
                    if key not in columns:
                        columns.append(key)
            document.protocol_rows = rows
            document.protocol_columns = columns

        # результаты_* — на вкладку "Результаты" (сгруппированы по
        # дисциплине, внутри каждой может быть несколько отдельных таблиц,
        # например по группам R4/R6 × мужчины/женщины), остальные типы —
        # на "Протоколы".
        if document.doc_type in result_doc_types:
            results_by_type.setdefault(document.doc_type, []).append(document)
        else:
            documents_by_type.setdefault(document.doc_type, []).append(document)

    results_groups = [
        {'doc_type': doc_type, 'label': label, 'docs': results_by_type[doc_type]}
        for doc_type, label in RESULT_DISCIPLINES
        if doc_type in results_by_type
    ]

    return render_template(
        'competitions/detail.html',
        competition=competition,
        documents_by_type=documents_by_type,
        results_groups=results_groups,
    )
