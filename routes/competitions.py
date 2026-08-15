"""Соревнования: календарный план, текущие, архив, страница соревнования."""
import json
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import extract

from models import (
    Competition, CompetitionApplication, CompetitionApplicationAthlete,
    CompetitionDocument, RegionalFederation, db,
)

bp = Blueprint('competitions', __name__)

BOAT_CLASSES = ['R4', 'R6']
DISCIPLINES = ['Спринт', 'Параллельный спринт', 'Слалом', 'Длинная гонка', 'Многоборье']

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


def _federation_logo_lookup():
    """Логотип направляющей организации на «Команды» берём из логотипа
    региональной федерации с тем же названием — своего логотипа у заявки
    нет (см. events._federation_logo_lookup — та же логика)."""
    return {
        rf.name.strip().lower(): rf.logo_path
        for rf in RegionalFederation.query.filter(RegionalFederation.logo_path.isnot(None)).all()
    }


def _match_logo(lookup, organization_name):
    if not organization_name:
        return None
    return lookup.get(organization_name.strip().lower())


@bp.route('/<int:competition_id>')
def detail(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    applications = (
        CompetitionApplication.query.filter_by(competition_id=competition_id)
        .order_by(CompetitionApplication.created_at.desc())
        .all()
    )
    total_athletes = sum(len(a.athletes) for a in applications)
    can_submit_application = (
        current_user.is_authenticated and current_user.role in ('region_rep', 'admin')
    )
    logo_lookup = _federation_logo_lookup()
    application_logos = {a.id: _match_logo(logo_lookup, a.org_name) for a in applications}
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
        applications=applications, total_athletes=total_athletes,
        can_submit_application=can_submit_application, application_logos=application_logos,
    )


def _can_manage(application):
    return current_user.is_authenticated and (
        current_user.role == 'admin' or application.submitted_by_id == current_user.id
    )


@bp.route('/<int:competition_id>/applications/<int:application_id>/view')
def application_view(competition_id, application_id):
    competition = Competition.query.get_or_404(competition_id)
    application = CompetitionApplication.query.get_or_404(application_id)
    if application.competition_id != competition.id:
        abort(404)
    logo_path = _match_logo(_federation_logo_lookup(), application.org_name)
    return render_template(
        'competitions/application_detail.html', competition=competition, application=application,
        can_manage=_can_manage(application), logo_path=logo_path,
    )


def _apply_athletes(application_id, form):
    last_names = form.getlist('athlete_last_name[]')
    first_names = form.getlist('athlete_first_name[]')
    middle_names = form.getlist('athlete_middle_name[]')
    genders = form.getlist('athlete_gender[]')
    birth_dates = form.getlist('athlete_birth_date[]')
    qualifications = form.getlist('athlete_qualification[]')
    age_groups = form.getlist('athlete_age_group[]')
    order_numbers = form.getlist('athlete_order_number[]')
    insurance_numbers = form.getlist('athlete_insurance_number[]')

    for i, last_name in enumerate(last_names):
        last_name = last_name.strip()
        first_name = (first_names[i].strip() if i < len(first_names) else '')
        if not last_name or not first_name:
            continue
        birth_date = None
        if i < len(birth_dates) and birth_dates[i]:
            try:
                birth_date = date.fromisoformat(birth_dates[i])
            except ValueError:
                birth_date = None
        db.session.add(CompetitionApplicationAthlete(
            application_id=application_id,
            last_name=last_name,
            first_name=first_name,
            middle_name=(middle_names[i].strip() or None) if i < len(middle_names) else None,
            gender=(genders[i].strip() or None) if i < len(genders) else None,
            birth_date=birth_date,
            qualification=(qualifications[i].strip() or None) if i < len(qualifications) else None,
            age_group=(age_groups[i].strip() or None) if i < len(age_groups) else None,
            order_number=(order_numbers[i].strip() or None) if i < len(order_numbers) else None,
            insurance_number=(insurance_numbers[i].strip() or None) if i < len(insurance_numbers) else None,
        ))


def _athletes_payload(application):
    if not application:
        return []
    return [
        {
            'last_name': a.last_name,
            'first_name': a.first_name,
            'middle_name': a.middle_name,
            'gender': a.gender,
            'birth_date': a.birth_date.isoformat() if a.birth_date else '',
            'qualification': a.qualification,
            'age_group': a.age_group,
            'order_number': a.order_number,
            'insurance_number': a.insurance_number,
        }
        for a in application.athletes
    ]


def _regional_federations():
    return RegionalFederation.query.order_by(RegionalFederation.name).all()


def _fill_application_fields(application, form):
    application.region = form.get('region', '').strip() or None
    application.team_name = form.get('team_name', '').strip() or None
    application.boat_class = form.get('boat_class', '').strip() or None
    application.discipline = form.get('discipline', '').strip() or None
    application.org_name = form.get('org_name', '').strip() or None
    application.org_leader_name = form.get('org_leader_name', '').strip() or None
    application.org_leader_position = form.get('org_leader_position', '').strip() or None
    application.org_leader_phone = form.get('org_leader_phone', '').strip() or None
    application.org_leader_email = form.get('org_leader_email', '').strip() or None
    application.coach_full_name = form.get('coach_full_name', '').strip() or None
    application.coach_phone = form.get('coach_phone', '').strip() or None
    application.coach_email = form.get('coach_email', '').strip() or None


@bp.route('/<int:competition_id>/applications/new', methods=['GET', 'POST'])
@login_required
def application_new(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if current_user.role not in ('region_rep', 'admin'):
        abort(403)

    if request.method == 'POST':
        last_names = request.form.getlist('athlete_last_name[]')
        if not any(name.strip() for name in last_names):
            flash('Добавьте хотя бы одного спортсмена.', 'error')
            return render_template(
                'competitions/application_form.html', competition=competition, application=None,
                existing_athletes=[], regional_federations=_regional_federations(),
                boat_classes=BOAT_CLASSES, disciplines=DISCIPLINES,
            )

        application = CompetitionApplication(
            competition_id=competition.id, submitted_by_id=current_user.id, origin='site',
        )
        _fill_application_fields(application, request.form)
        db.session.add(application)
        db.session.flush()
        _apply_athletes(application.id, request.form)
        db.session.commit()

        flash('Заявка сохранена.', 'success')
        return redirect(url_for('competitions.detail', competition_id=competition.id) + '#tab-entries')

    return render_template(
        'competitions/application_form.html', competition=competition, application=None,
        existing_athletes=[], regional_federations=_regional_federations(),
        boat_classes=BOAT_CLASSES, disciplines=DISCIPLINES,
    )


@bp.route('/<int:competition_id>/applications/<int:application_id>/edit', methods=['GET', 'POST'])
@login_required
def application_edit(competition_id, application_id):
    competition = Competition.query.get_or_404(competition_id)
    application = CompetitionApplication.query.get_or_404(application_id)
    if application.competition_id != competition.id:
        abort(404)
    if not _can_manage(application):
        abort(403)

    if request.method == 'POST':
        last_names = request.form.getlist('athlete_last_name[]')
        if not any(name.strip() for name in last_names):
            flash('Добавьте хотя бы одного спортсмена.', 'error')
            return render_template(
                'competitions/application_form.html', competition=competition, application=application,
                existing_athletes=_athletes_payload(application), regional_federations=_regional_federations(),
                boat_classes=BOAT_CLASSES, disciplines=DISCIPLINES,
            )

        _fill_application_fields(application, request.form)
        application.updated_at = datetime.utcnow()
        CompetitionApplicationAthlete.query.filter_by(application_id=application.id).delete()
        _apply_athletes(application.id, request.form)
        db.session.commit()

        flash('Заявка обновлена.', 'success')
        return redirect(url_for('competitions.detail', competition_id=competition.id) + '#tab-entries')

    return render_template(
        'competitions/application_form.html', competition=competition, application=application,
        existing_athletes=_athletes_payload(application), regional_federations=_regional_federations(),
        boat_classes=BOAT_CLASSES, disciplines=DISCIPLINES,
    )


@bp.route('/<int:competition_id>/applications/<int:application_id>/delete', methods=['POST'])
@login_required
def application_delete(competition_id, application_id):
    application = CompetitionApplication.query.get_or_404(application_id)
    if application.competition_id != competition_id:
        abort(404)
    if not _can_manage(application):
        abort(403)

    db.session.delete(application)
    db.session.commit()
    flash('Заявка удалена.', 'success')
    return redirect(url_for('competitions.detail', competition_id=competition_id) + '#tab-entries')
