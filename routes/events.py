"""Мероприятия: семинары судей, тренеров, руководителей."""
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import Event, SeminarApplicationSubmission, SeminarApplicationSubmissionParticipant, db
from sync_to_referee import отправить_заявку, запросить_заявки

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


@bp.route('/')
def index():
    event_type = request.args.get('event_type', '')

    query = Event.query
    if event_type:
        query = query.filter_by(event_type=event_type)

    events = query.order_by(Event.start_date.desc()).all()

    return render_template(
        'events/list.html',
        events=events,
        selected_event_type=event_type,
    )


@bp.route('/<int:event_id>')
def detail(event_id):
    event = Event.query.get_or_404(event_id)
    applications, applications_error = (
        запросить_заявки(event.source_id) if event.source_id else ([], None)
    )
    can_submit_application = (
        current_user.is_authenticated and current_user.role in ('region_rep', 'admin')
    )
    return render_template(
        'events/detail.html', event=event,
        applications=applications, applications_error=applications_error,
        can_submit_application=can_submit_application,
    )


@bp.route('/<int:event_id>/applications/new', methods=['GET', 'POST'])
@login_required
def application_new(event_id):
    event = Event.query.get_or_404(event_id)
    if current_user.role not in ('region_rep', 'admin'):
        abort(403)
    if not event.source_id:
        flash('Это мероприятие не синхронизировано с SPORTS_REFEREE — заявку подать нельзя.', 'error')
        return redirect(url_for('events.detail', event_id=event.id))

    if request.method == 'POST':
        full_names = request.form.getlist('participant_full_name[]')
        if not any(name.strip() for name in full_names):
            flash('Добавьте хотя бы одного участника.', 'error')
            return render_template(
                'events/application_form.html', event=event,
                judge_qualifications=JUDGE_QUALIFICATIONS, seminar_categories=SEMINAR_CATEGORIES,
                specializations=SEMINAR_PARTICIPANT_SPECIALIZATIONS,
            )

        submission = SeminarApplicationSubmission(
            event_id=event.id,
            submitted_by_id=current_user.id,
            region=request.form.get('region', '').strip() or None,
            organization_name=request.form.get('organization_name', '').strip() or None,
            sending_org_name=request.form.get('sending_org_name', '').strip() or None,
            sending_org_leader_name=request.form.get('sending_org_leader_name', '').strip() or None,
            sending_org_leader_position=request.form.get('sending_org_leader_position', '').strip() or None,
            sending_org_leader_phone=request.form.get('sending_org_leader_phone', '').strip() or None,
            sending_org_leader_email=request.form.get('sending_org_leader_email', '').strip() or None,
        )
        db.session.add(submission)
        db.session.flush()

        genders = request.form.getlist('participant_gender[]')
        birth_dates = request.form.getlist('participant_birth_date[]')
        qualifications = request.form.getlist('participant_qualification[]')
        categories = request.form.getlist('participant_category[]')
        specializations = request.form.getlist('participant_specialization[]')
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
                submission_id=submission.id,
                full_name=full_name,
                gender=(genders[i].strip() or None) if i < len(genders) else None,
                birth_date=birth_date,
                judge_qualification=(qualifications[i].strip() or None) if i < len(qualifications) else None,
                assigned_category=(categories[i].strip() or None) if i < len(categories) else None,
                specialization=(specializations[i].strip() or None) if i < len(specializations) else None,
            ))
        db.session.commit()

        success, message, referee_application_id = отправить_заявку(submission, event.source_id)
        submission.send_status = 'sent' if success else 'failed'
        submission.send_message = message
        submission.referee_application_id = referee_application_id
        db.session.commit()

        flash('Заявка сохранена. ' + message, 'success' if success else 'danger')
        return redirect(url_for('events.detail', event_id=event.id))

    return render_template(
        'events/application_form.html', event=event,
        judge_qualifications=JUDGE_QUALIFICATIONS, seminar_categories=SEMINAR_CATEGORIES,
        specializations=SEMINAR_PARTICIPANT_SPECIALIZATIONS,
    )
