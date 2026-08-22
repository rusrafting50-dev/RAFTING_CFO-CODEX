"""Региональные федерации субъектов ЦФО."""
from flask import Blueprint, abort, render_template, url_for

from models import Athlete, Club, Referee, RegionalFederation

bp = Blueprint('regions', __name__)

# Разделы бокового меню «О федерации» на персональной странице федерации.
# Для goals/contacts есть реальные поля в RegionalFederation, для team —
# реальные данные из REGTEAM_RAFTING (см. section() ниже); для остальных
# пока нет своей модели данных — раздел открывается с заглушкой
# «материалы пока не добавлены», как и на других страницах сайта, где
# источник данных ещё не подключён.
SECTIONS = [
    ('goals', 'Цели и задачи'),
    ('leadership', 'Руководство'),
    ('committees', 'Комитеты и комиссии'),
    ('clubs', 'Клубы'),
    ('team', 'Сборная команда'),
    ('referees', 'Спортивные судьи'),
    ('calendar', 'Календарный план'),
    ('documents', 'Документы'),
    ('contacts', 'Контакты'),
]
SECTION_KEYS = {key for key, _ in SECTIONS}


def _sidebar_items(region, active_section):
    """Пункты бокового меню «О федерации»: первым — «Федерация» (ссылка
    на обзорную страницу), затем разделы. active — текущий пункт, он
    выводится как заголовок-плашка вместо обычной строки."""
    items = [{
        'label': 'Федерация',
        'url': url_for('regions.detail', region_id=region.id),
        'active': active_section is None,
    }]
    for key, label in SECTIONS:
        items.append({
            'label': label,
            'url': url_for('regions.section', region_id=region.id, section=key),
            'active': active_section == key,
        })
    return items


@bp.route('/')
def index():
    regional_federations = RegionalFederation.query.order_by(RegionalFederation.name).all()
    return render_template('regions/list.html', regional_federations=regional_federations)


@bp.route('/<int:region_id>')
def detail(region_id):
    region = RegionalFederation.query.get_or_404(region_id)
    return render_template('regions/detail.html', region=region, sidebar_items=_sidebar_items(region, None))


@bp.route('/<int:region_id>/<section>')
def section(region_id, section):
    if section not in SECTION_KEYS:
        abort(404)
    region = RegionalFederation.query.get_or_404(region_id)
    section_label = dict(SECTIONS)[section]

    region_clubs = []
    if section == 'clubs':
        region_clubs = Club.query.filter_by(region_id=region.id).order_by(Club.name).all()

    region_referees = []
    if section == 'referees' and region.subject_name:
        # Territory у Referee — сразу наименование субъекта РФ (Judge.region
        # в SPORTS_REFEREE), а не внутренний район, поэтому сравниваем
        # напрямую, без привязки к клубам (в отличие от team_athletes ниже —
        # у судей нет понятия «состоит в клубе»).
        subject_name = region.subject_name.strip().lower()
        region_referees = sorted(
            (
                r for r in Referee.query.filter(Referee.is_active.is_(True)).all()
                if r.territory and r.territory.strip().lower() == subject_name
            ),
            key=lambda r: r.full_name,
        )

    team_athletes = []
    if section == 'team' and region.subject_name:
        # Сравнение без учёта регистра делается в Python, а не в SQL —
        # LOWER() в SQLite работает только для ASCII и не переводит
        # кириллицу в нижний регистр, из-за чего сравнение по regionу
        # молча не находило бы совпадений.
        subject_name = region.subject_name.strip().lower()
        # В сборную команду попадают только те, кто состоит в каком-то
        # клубе (Club.name совпадает с Athlete.organization) — состав
        # клуба первичен, включение в сборную зависит от него, а не
        # наоборот (см. соответствующие разделы «Тренеры»/«Спортсмены»
        # на странице клуба, routes/clubs.py.section()).
        club_names = {c.name.strip().lower() for c in Club.query.all()}
        team_athletes = sorted(
            (
                a for a in Athlete.query.filter(Athlete.is_active.is_(True)).all()
                if a.territory and a.territory.strip().lower() == subject_name
                and a.organization and a.organization.strip().lower() in club_names
            ),
            key=lambda a: (a.role or '', a.full_name),
        )

    return render_template(
        'regions/section.html', region=region, sidebar_items=_sidebar_items(region, section),
        section=section, section_label=section_label, team_athletes=team_athletes,
        region_clubs=region_clubs, region_referees=region_referees,
    )
