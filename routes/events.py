"""Мероприятия: семинары судей, тренеров, руководителей."""
from flask import Blueprint, render_template, request

from models import Event

bp = Blueprint('events', __name__)


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
    return render_template('events/detail.html', event=event)
