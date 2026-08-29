"""Спортивные клубы и организации рафтинга в ЦФО."""
from itertools import groupby

from flask import Blueprint, abort, render_template, request, url_for

from models import Athlete, Club, RegionalFederation
from routes.regions import TEAM_CATEGORIES_BY_GENDER, TEAM_GENDERS

bp = Blueprint('clubs', __name__)

# section -> роль Athlete.role, которую показываем в этом разделе.
SECTION_ATHLETE_ROLES = {'coaches': 'тренер', 'athletes': 'спортсмен'}

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

    club_athletes = []
    team_gender = team_category = team_genders = team_categories = None
    role = SECTION_ATHLETE_ROLES.get(section)
    if role:
        # Принадлежность клубу и включение в сборную — независимые вещи:
        # исключённый из сборной (is_active=False) спортсмен/тренер всё
        # равно остаётся в составе клуба, поэтому здесь фильтра по
        # is_active нет (в отличие от routes/regions.py.section() —
        # раздел «Сборная команда» федерации показывает только активных).
        # 'athletes' — все спортсмены клуба, независимо от того, состоят
        # ли они в сборной, точно так же.
        #
        # Сравнение без учёта регистра — в Python, не в SQL: LOWER() в
        # SQLite не переводит кириллицу в нижний регистр (см. тот же
        # приём в routes/regions.py.section()).
        club_name = club.name.strip().lower()
        role_athletes = [
            a for a in Athlete.query.filter(Athlete.role == role).all()
            if a.organization and a.organization.strip().lower() == club_name
        ]

        if section == 'athletes':
            # Та же сетка пол/возрастная категория, что на «Сборная
            # команда» страницы федерации (routes/regions.py.section()) —
            # оформление специально одинаковое, поэтому и разбивка та же.
            team_gender = request.args.get('gender')
            if team_gender not in TEAM_CATEGORIES_BY_GENDER:
                team_gender = 'мужские'
            team_categories = TEAM_CATEGORIES_BY_GENDER[team_gender]
            team_category = request.args.get('category')
            if team_category not in team_categories:
                team_category = team_categories[0]
            team_genders = TEAM_GENDERS

            category_lower = team_category.strip().lower()
            club_athletes = sorted(
                (a for a in role_athletes if a.national_team and a.national_team.strip().lower() == category_lower),
                key=lambda a: a.full_name,
            )
        else:
            club_athletes = sorted(role_athletes, key=lambda a: a.full_name)

    return render_template(
        'clubs/section.html', club=club, sidebar_items=_sidebar_items(club, section),
        section=section, section_label=section_label, club_athletes=club_athletes,
        team_gender=team_gender, team_category=team_category,
        team_genders=team_genders, team_categories=team_categories,
    )
