"""Мероприятия: семинары судей, тренеров, руководителей."""
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import extract

from models import (
    Document, DocumentCategory, DocumentSection, Event, RegionalFederation,
    SeminarApplicationSubmission, SeminarApplicationSubmissionParticipant, db,
)

bp = Blueprint('events', __name__)

# Те же справочники, что в SPORTS_REFEREE (references.py) — держим здесь
# отдельной копией, так как это независимо разворачиваемый проект.
JUDGE_QUALIFICATIONS = ['ССВК', 'СС1К', 'СС2К', 'СС3К']
SEMINAR_CATEGORIES = ['Всероссийская', 'Первая', 'Вторая', 'Третья', 'Юный судья']
SEMINAR_PARTICIPANT_SPECIALIZATIONS = [
    'Секретариат, информация',
    'Судейство, дистанции',
    'Секретариат, информация, Судейство, дистанции',
]

# Вторая строка меню на странице «Мероприятия — Календарный план».
# 'спортивная_подготовка' — новый тип, площадка для него на сайте уже
# есть, а данные придут от SPORTS_REFEREE отдельным довеском к
# существующей синхронизации (routes/api.py принимает event_type любой
# строкой, без ограничения списком).
EVENT_TYPE_FILTERS = [
    ('семинар_судей', 'Спортивные судьи'),
    ('семинар_тренеров', 'Тренеры'),
    ('спортивная_подготовка', 'Спортивная подготовка'),
    ('семинар_руководителей', 'Руководители организаций'),
]


@bp.route('/')
def index():
    """Мероприятия — календарный план текущего года + ссылки в архив
    трёх предыдущих лет (по образцу competitions.calendar)."""
    event_type = request.args.get('event_type', '')
    year = date.today().year

    query = Event.query.filter(extract('year', Event.start_date) == year)
    if event_type:
        query = query.filter_by(event_type=event_type)

    events = query.order_by(Event.start_date.asc()).all()
    archive_years = [year - 1, year - 2, year - 3]

    return render_template(
        'events/list.html',
        events=events, selected_event_type=event_type,
        event_type_filters=EVENT_TYPE_FILTERS, year=year, archive_years=archive_years,
    )


@bp.route('/archive')
def archive():
    event_type = request.args.get('event_type', '')
    year = request.args.get('year', type=int)

    query = Event.query
    if event_type:
        query = query.filter_by(event_type=event_type)
    if year:
        query = query.filter(extract('year', Event.start_date) == year)
    else:
        query = query.filter(Event.start_date < date.today())

    events = query.order_by(Event.start_date.desc()).all()

    years = sorted(
        {e.start_date.year for e in Event.query.all() if e.start_date},
        reverse=True,
    )

    return render_template(
        'events/archive.html',
        events=events, selected_event_type=event_type,
        years=years, selected_year=year,
    )


@bp.route('/documents')
def documents():
    """Методические материалы под Мероприятия — та же страница-список, что
    Соревнования/Нормативные документы (competitions.documents), но со
    своим боковым меню категорий (scope='мероприятия').

    Документ появляется здесь, если при загрузке в админке ему назначили
    категорию из этого меню (Document.doc_category — совпадение по
    названию категории) и/или конкретный раздел внутри неё
    (Document.section_id) — раздел не обязателен, самой категории
    достаточно.

    Имя категории уникально только в пределах своего scope (см.
    DocumentCategory) — у страницы федерации (scope='федерация') есть
    категории с такими же названиями, поэтому здесь дополнительно
    исключаются документы, у которых задан region_id (те принадлежат
    конкретной федерации, а не этой, общей для всего сайта, странице)."""
    categories = (
        DocumentCategory.query.filter_by(scope='мероприятия')
        .order_by(DocumentCategory.name)
        .all()
    )
    category_names = [category.name for category in categories]
    section_ids = [section.id for category in categories for section in category.sections]

    selected_section_id = request.args.get('section', type=int)
    selected_section = DocumentSection.query.get(selected_section_id) if selected_section_id else None

    selected_category = None
    if not selected_section:
        selected_category_id = request.args.get('category', type=int)
        if selected_category_id:
            selected_category = next((c for c in categories if c.id == selected_category_id), None)

    query = (
        Document.query.filter(Document.region_id.is_(None))
        .order_by(Document.uploaded_at.desc(), Document.title)
    )

    if selected_section:
        documents_ = query.filter_by(section_id=selected_section.id).all()
    elif selected_category:
        category_section_ids = [s.id for s in selected_category.sections]
        conditions = [Document.doc_category == selected_category.name]
        if category_section_ids:
            conditions.append(Document.section_id.in_(category_section_ids))
        documents_ = query.filter(db.or_(*conditions)).all()
    elif category_names or section_ids:
        conditions = []
        if category_names:
            conditions.append(Document.doc_category.in_(category_names))
        if section_ids:
            conditions.append(Document.section_id.in_(section_ids))
        documents_ = query.filter(db.or_(*conditions)).all()
    else:
        documents_ = []

    return render_template(
        'events/documents.html', documents=documents_, categories=categories,
        selected_section=selected_section, selected_category=selected_category,
    )


def _federation_logo_lookup():
    """Логотип направляющей организации на «Участники» берём из логотипа
    региональной федерации с тем же названием (RegionalFederation.name —
    то же самое поле, что «Наименование региональной спортивной федерации»
    в форме заявки) — своего логотипа у заявки нет."""
    return {
        rf.name.strip().lower(): rf.logo_path
        for rf in RegionalFederation.query.filter(RegionalFederation.logo_path.isnot(None)).all()
    }


def _match_logo(lookup, organization_name):
    if not organization_name:
        return None
    return lookup.get(organization_name.strip().lower())


@bp.route('/<int:event_id>')
def detail(event_id):
    event = Event.query.get_or_404(event_id)
    applications = (
        SeminarApplicationSubmission.query.filter_by(event_id=event.id)
        .order_by(SeminarApplicationSubmission.created_at.desc())
        .all()
    )
    total_participants = sum(len(a.participants) for a in applications)
    can_submit_application = (
        current_user.is_authenticated and current_user.role in ('region_rep', 'admin')
    )
    logo_lookup = _federation_logo_lookup()
    application_logos = {a.id: _match_logo(logo_lookup, a.organization_name) for a in applications}
    return render_template(
        'events/detail.html', event=event,
        applications=applications, total_participants=total_participants,
        can_submit_application=can_submit_application, application_logos=application_logos,
    )


def _can_manage(submission):
    return current_user.is_authenticated and (
        current_user.role == 'admin' or submission.submitted_by_id == current_user.id
    )


@bp.route('/<int:event_id>/applications/<int:submission_id>/view')
def application_view(event_id, submission_id):
    event = Event.query.get_or_404(event_id)
    submission = SeminarApplicationSubmission.query.get_or_404(submission_id)
    if submission.event_id != event.id:
        abort(404)
    logo_path = _match_logo(_federation_logo_lookup(), submission.organization_name)
    return render_template(
        'events/application_detail.html', event=event, submission=submission,
        can_manage=_can_manage(submission), logo_path=logo_path,
    )


def _apply_participants(submission_id, form):
    full_names = form.getlist('participant_full_name[]')
    genders = form.getlist('participant_gender[]')
    birth_dates = form.getlist('participant_birth_date[]')
    qualifications = form.getlist('participant_qualification[]')
    categories = form.getlist('participant_category[]')
    specializations = form.getlist('participant_specialization[]')

    for i, full_name in enumerate(full_names):
        full_name = full_name.strip()
        if not full_name:
            continue
        birth_date = None
        if i < len(birth_dates) and birth_dates[i]:
            try:
                birth_date = date.fromisoformat(birth_dates[i])
            except ValueError:
                birth_date = None
        db.session.add(SeminarApplicationSubmissionParticipant(
            submission_id=submission_id,
            full_name=full_name,
            gender=(genders[i].strip() or None) if i < len(genders) else None,
            birth_date=birth_date,
            judge_qualification=(qualifications[i].strip() or None) if i < len(qualifications) else None,
            assigned_category=(categories[i].strip() or None) if i < len(categories) else None,
            specialization=(specializations[i].strip() or None) if i < len(specializations) else None,
        ))


def _participants_payload(submission):
    if not submission:
        return []
    return [
        {
            'full_name': p.full_name,
            'gender': p.gender,
            'birth_date': p.birth_date.isoformat() if p.birth_date else '',
            'judge_qualification': p.judge_qualification,
            'assigned_category': p.assigned_category,
            'specialization': p.specialization,
        }
        for p in submission.participants
    ]


def _regional_federations():
    return RegionalFederation.query.order_by(RegionalFederation.name).all()


def _fill_submission_fields(submission, form):
    submission.region = form.get('region', '').strip() or None
    submission.organization_name = form.get('organization_name', '').strip() or None
    submission.sending_org_name = form.get('sending_org_name', '').strip() or None
    submission.sending_org_leader_name = form.get('sending_org_leader_name', '').strip() or None
    submission.sending_org_leader_position = form.get('sending_org_leader_position', '').strip() or None
    submission.sending_org_leader_phone = form.get('sending_org_leader_phone', '').strip() or None
    submission.sending_org_leader_email = form.get('sending_org_leader_email', '').strip() or None


@bp.route('/<int:event_id>/applications/new', methods=['GET', 'POST'])
@login_required
def application_new(event_id):
    event = Event.query.get_or_404(event_id)
    if current_user.role not in ('region_rep', 'admin'):
        abort(403)

    if request.method == 'POST':
        full_names = request.form.getlist('participant_full_name[]')
        if not any(name.strip() for name in full_names):
            flash('Добавьте хотя бы одного участника.', 'error')
            return render_template(
                'events/application_form.html', event=event, submission=None,
                existing_participants=[], regional_federations=_regional_federations(),
                judge_qualifications=JUDGE_QUALIFICATIONS, seminar_categories=SEMINAR_CATEGORIES,
                specializations=SEMINAR_PARTICIPANT_SPECIALIZATIONS,
            )

        submission = SeminarApplicationSubmission(
            event_id=event.id, submitted_by_id=current_user.id, origin='site',
        )
        _fill_submission_fields(submission, request.form)
        db.session.add(submission)
        db.session.flush()
        _apply_participants(submission.id, request.form)
        db.session.commit()

        flash('Заявка сохранена.', 'success')
        return redirect(url_for('events.detail', event_id=event.id))

    return render_template(
        'events/application_form.html', event=event, submission=None,
        existing_participants=[], regional_federations=_regional_federations(),
        judge_qualifications=JUDGE_QUALIFICATIONS, seminar_categories=SEMINAR_CATEGORIES,
        specializations=SEMINAR_PARTICIPANT_SPECIALIZATIONS,
    )


@bp.route('/<int:event_id>/applications/<int:submission_id>/edit', methods=['GET', 'POST'])
@login_required
def application_edit(event_id, submission_id):
    event = Event.query.get_or_404(event_id)
    submission = SeminarApplicationSubmission.query.get_or_404(submission_id)
    if submission.event_id != event.id:
        abort(404)
    if not _can_manage(submission):
        abort(403)

    if request.method == 'POST':
        full_names = request.form.getlist('participant_full_name[]')
        if not any(name.strip() for name in full_names):
            flash('Добавьте хотя бы одного участника.', 'error')
            return render_template(
                'events/application_form.html', event=event, submission=submission,
                existing_participants=_participants_payload(submission), regional_federations=_regional_federations(),
                judge_qualifications=JUDGE_QUALIFICATIONS, seminar_categories=SEMINAR_CATEGORIES,
                specializations=SEMINAR_PARTICIPANT_SPECIALIZATIONS,
            )

        _fill_submission_fields(submission, request.form)
        submission.updated_at = datetime.utcnow()
        SeminarApplicationSubmissionParticipant.query.filter_by(submission_id=submission.id).delete()
        _apply_participants(submission.id, request.form)
        db.session.commit()

        flash('Заявка обновлена.', 'success')
        return redirect(url_for('events.detail', event_id=event.id))

    return render_template(
        'events/application_form.html', event=event, submission=submission,
        existing_participants=_participants_payload(submission), regional_federations=_regional_federations(),
        judge_qualifications=JUDGE_QUALIFICATIONS, seminar_categories=SEMINAR_CATEGORIES,
        specializations=SEMINAR_PARTICIPANT_SPECIALIZATIONS,
    )


@bp.route('/<int:event_id>/applications/<int:submission_id>/delete', methods=['POST'])
@login_required
def application_delete(event_id, submission_id):
    submission = SeminarApplicationSubmission.query.get_or_404(submission_id)
    if submission.event_id != event_id:
        abort(404)
    if not _can_manage(submission):
        abort(403)

    db.session.delete(submission)
    db.session.commit()
    flash('Заявка удалена.', 'success')
    return redirect(url_for('events.detail', event_id=event_id))
