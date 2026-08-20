"""Спортивные клубы и организации рафтинга в ЦФО."""
from itertools import groupby

from flask import Blueprint, abort, render_template, url_for

from models import Club, RegionalFederation

bp = Blueprint('clubs', __name__)

# Разделы бокового меню на персональной странице клуба — тот же приём,
# что regions.SECTIONS/_sidebar_items для региональной федерации.
SECTIONS = [
    ('leadership', 'Руководство'),
    ('coaches', 'Тренеры'),
    ('athletes', 'Спортсмены'),
    ('schedule', 'Расписание занятий'),
    ('achievements', 'Достижения'),
    ('contacts', 'Контакты'),
]
SECTION_KEYS = {key for key, _ in SECTIONS}


def _sidebar_items(club, active_section):
    items = [{
        'label': 'Клуб',
        'url': url_for('clubs.detail', club_id=club.id),
        'active': active_section is None,
    }]
    for key, label in SECTIONS:
        items.append({
            'label': label,
            'url': url_for('clubs.section', club_id=club.id, section=key),
            'active': active_section == key,
        })
    return items


@bp.route('/')
def index():
    clubs = (
        Club.query.join(RegionalFederation, Club.region_id == RegionalFederation.id)
        .order_by(RegionalFederation.name, Club.name)
        .all()
    )
    groups = [(region, list(region_clubs)) for region, region_clubs in groupby(clubs, key=lambda c: c.region)]
    return render_template('clubs/list.html', groups=groups)


@bp.route('/<int:club_id>')
def detail(club_id):
    club = Club.query.get_or_404(club_id)
    return render_template('clubs/detail.html', club=club, sidebar_items=_sidebar_items(club, None))


@bp.route('/<int:club_id>/<section>')
def section(club_id, section):
    if section not in SECTION_KEYS:
        abort(404)
    club = Club.query.get_or_404(club_id)
    section_label = dict(SECTIONS)[section]
    return render_template(
        'clubs/section.html', club=club, sidebar_items=_sidebar_items(club, section),
        section=section, section_label=section_label,
    )
