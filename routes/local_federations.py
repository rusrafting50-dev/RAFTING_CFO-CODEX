"""Местные спортивные федерации — третий уровень структуры сайта
(ЦФО → Региональная федерация → Местная федерация), параллельно Club.
Персональная страница по структуре и оформлению повторяет
RegionalFederation/Club (см. routes/clubs.py — тот же приём: обзорная
страница + разделы через один общий <section> маршрут, боковое меню —
тот же шаблон regions/_sidebar.html/clubs/_sidebar.html, генерика по
sidebar_items)."""
from flask import Blueprint, abort, render_template, url_for

from models import FederationMember, LocalFederation

bp = Blueprint('local_federations', __name__)

# Группы состава (FederationMember.body) под разделом «Коллегии и
# советы» — та же группировка, что и на странице «О федерации» ЦФО
# (routes/federation.py: BODY_LABELS), но без 'исполком' — на местной
# федерации руководящий орган выведен в отдельный раздел «Руководство»
# (body='руководство').
COUNCIL_BODIES = ['коллегия_судей', 'тренерский_совет', 'комитет_представителей']
BODY_LABELS = {
    'коллегия_судей': 'Коллегия судей',
    'тренерский_совет': 'Тренерский совет',
    'комитет_представителей': 'Комитет представителей',
}

# Разделы бокового меню персональной страницы местной федерации — тот
# же приём, что clubs.SECTIONS/_sidebar_items.
SECTIONS = [
    ('leadership', 'Руководство'),
    ('members', 'Члены Федерации'),
    ('councils', 'Коллегии и советы'),
    ('calendar', 'Календарный план'),
    ('clubs', 'Клубы'),
    ('contacts', 'Контакты'),
]
SECTION_KEYS = {key for key, _ in SECTIONS}


def _sidebar_items(local_federation, active_section):
    items = [{
        'label': 'Местная спортивная федерация',
        'url': url_for('local_federations.detail', local_federation_id=local_federation.id),
        'active': active_section is None,
    }]
    for key, label in SECTIONS:
        items.append({
            'label': label,
            'url': url_for('local_federations.section', local_federation_id=local_federation.id, section=key),
            'active': active_section == key,
        })
    return items


@bp.route('/<int:local_federation_id>')
def detail(local_federation_id):
    local_federation = LocalFederation.query.get_or_404(local_federation_id)
    return render_template(
        'local_federations/detail.html', local_federation=local_federation,
        sidebar_items=_sidebar_items(local_federation, None),
    )


@bp.route('/<int:local_federation_id>/<section>')
def section(local_federation_id, section):
    if section not in SECTION_KEYS:
        abort(404)
    local_federation = LocalFederation.query.get_or_404(local_federation_id)
    section_label = dict(SECTIONS)[section]

    members_by_body = {}
    if section in ('leadership', 'members', 'councils'):
        bodies = {
            'leadership': ['руководство'],
            'members': ['член_федерации'],
            'councils': COUNCIL_BODIES,
        }[section]
        members = (
            FederationMember.query
            .filter(FederationMember.local_federation_id == local_federation.id, FederationMember.body.in_(bodies))
            .order_by(FederationMember.body, FederationMember.full_name)
            .all()
        )
        for member in members:
            members_by_body.setdefault(member.body, []).append(member)

    return render_template(
        'local_federations/section.html', local_federation=local_federation,
        sidebar_items=_sidebar_items(local_federation, section),
        section=section, section_label=section_label,
        members_by_body=members_by_body, body_labels=BODY_LABELS,
    )
