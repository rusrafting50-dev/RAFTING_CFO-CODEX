"""Региональные федерации субъектов ЦФО."""
from flask import Blueprint, abort, render_template

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


@bp.route('/')
def index():
    regional_federations = RegionalFederation.query.order_by(RegionalFederation.name).all()
    return render_template('regions/list.html', regional_federations=regional_federations)


@bp.route('/<int:region_id>')
def detail(region_id):
    region = RegionalFederation.query.get_or_404(region_id)
    return render_template('regions/detail.html', region=region, sections=SECTIONS)


@bp.route('/<int:region_id>/<section>')
def section(region_id, section):
    if section not in SECTION_KEYS:
        abort(404)
    region = RegionalFederation.query.get_or_404(region_id)
    section_label = dict(SECTIONS)[section]
    return render_template(
        'regions/section.html', region=region, sections=SECTIONS,
        section=section, section_label=section_label,
    )
