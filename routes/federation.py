"""О федерации: описание, структура и органы управления."""
from flask import Blueprint, render_template

from models import FederationMember

bp = Blueprint('federation', __name__)

BODY_LABELS = {
    'исполком': 'Исполком',
    'коллегия_судей': 'Коллегия судей',
    'тренерский_совет': 'Тренерский совет',
    'комитет_представителей': 'Комитет представителей',
}


@bp.route('/')
def about():
    return render_template('federation/about.html')


@bp.route('/structure')
def structure():
    members = FederationMember.query.order_by(FederationMember.body, FederationMember.full_name).all()

    members_by_body = {}
    for member in members:
        members_by_body.setdefault(member.body, []).append(member)

    return render_template(
        'federation/structure.html',
        members_by_body=members_by_body,
        body_labels=BODY_LABELS,
    )
