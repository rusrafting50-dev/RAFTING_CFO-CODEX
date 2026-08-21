"""Региональные федерации субъектов ЦФО."""
from flask import Blueprint, abort, render_template, url_for

from models import RegionalFederation

bp = Blueprint('regions', __name__)

# Разделы бокового меню «О федерации» на персональной странице федерации.
# Для goals/contacts есть реальные поля в RegionalFederation; для
# остальных пока нет своей модели данных — раздел открывается с
# заглушкой «материалы пока не добавлены», как и на других страницах
# сайта, где источник данных ещё не подключён.
SECTIONS = [
    ('goals', 'Цели и задачи'),
    ('leadership', 'Руководство'),
    ('committees', 'Комитеты и комиссии'),
    ('clubs', 'Клубы'),
    ('calendar', 'Календарный план'),
    ('documents', 'Документы'),
    ('contacts', 'Контакты'),
]
SECTION_KEYS = {key for key, _ in SECTIONS}


def _sidebar_items(region, active_section):
    """Пункты бокового меню «О федерации»: первым — «Федерация» (ссылка
    на обзорную страницу), затем разделы, последним — «Спортивные
    судьи» (ссылка на общую по ЦФО страницу судей, а не раздел этой
    федерации, поэтому активной не бывает). active — текущий пункт, он
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
    items.append({
        'label': 'Спортивные судьи',
        'url': url_for('referees.index'),
        'active': False,
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
    return render_template(
        'regions/section.html', region=region, sidebar_items=_sidebar_items(region, section),
        section=section, section_label=section_label,
    )
