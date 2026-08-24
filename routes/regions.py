"""Региональные федерации субъектов ЦФО."""
from flask import Blueprint, abort, render_template, request, url_for

from models import Athlete, Club, Document, DocumentCategory, DocumentSection, RegionalFederation, db

bp = Blueprint('regions', __name__)

# «Функциональные» разделы бокового меню «О федерации» — со своими
# реальными данными (в отличие от категорий документов ниже). Для
# leadership/calendar пока нет своей модели данных — раздел открывается
# с заглушкой «материалы пока не добавлены», как и на других страницах
# сайта, где источник данных ещё не подключён; team — реальные данные
# из REGTEAM_RAFTING (см. section() ниже), contacts — поля RegionalFederation.
#
# 'clubs' сюда не входит: этот раздел убран из бокового меню «О
# федерации» по просьбе федерации, но сама страница остаётся рабочей —
# на неё по-прежнему ведёт пункт «Клубы» в шапке сайта и подвале
# (base.html), поэтому раздел/маршрут не удаляется, а только перестаёт
# быть пунктом этого меню.
FUNCTIONAL_SECTIONS = [
    ('leadership', 'Руководство'),
    ('calendar', 'Календарный план'),
    ('team', 'Сборная команда'),
    ('contacts', 'Контакты'),
]
FUNCTIONAL_SECTION_LABELS = dict(FUNCTIONAL_SECTIONS)
SECTION_KEYS = {key for key, _ in FUNCTIONAL_SECTIONS} | {'clubs'}

# Порядок пунктов бокового меню «О федерации» между «Федерация» вверху и
# «Все»/«Контакты» внизу — смесь категорий документов страницы федерации
# (scope='федерация', см. auth.py: FEDERATION_DOCUMENT_TAXONOMY) и
# функциональных разделов из FUNCTIONAL_SECTIONS. Задан федерацией.
FEDERATION_SIDEBAR_LAYOUT = [
    ('category', 'Направления деятельности'),
    ('category', 'Основополагающие документы'),
    ('functional', 'leadership'),
    ('category', 'Структура Федерации'),
    ('category', 'Лицензирование и сертификация'),
    ('functional', 'calendar'),
    ('category', 'Положение о межмуниципальных и региональных спортивных соревнованиях по виду спорта «рафтинг»'),
    ('functional', 'team'),
]


def _sidebar_items(region, active_section=None, active_category=None, active_doc_section=None):
    """Пункты бокового меню «О федерации»: «Федерация» вверху (ссылка на
    обзорную страницу), затем FEDERATION_SIDEBAR_LAYOUT, затем
    «Контакты» и «Все» (сбрасывает фильтр документов) — самыми
    последними.

    Категории документов (scope='федерация') с разделами рендерятся как
    раскрывающиеся пункты со своими разделами внутри (kind='category') —
    тот же приём, что doc-category-panel на «Соревнования → Нормативные
    документы»; категории без единого раздела (например, «Направления
    деятельности») — обычная ссылка-фильтр, без шеврона и пустой
    раскрывашки, как и функциональные разделы и «Контакты» (kind='link').
    Текущий пункт выводится не строкой списка, а плашкой-заголовком
    (см. regions/_sidebar.html)."""
    fed_categories = {
        category.name: category
        for category in DocumentCategory.query.filter_by(scope='федерация').all()
    }
    showing_documents = active_category is not None or active_doc_section is not None or active_section == 'all_documents'

    items = [{
        'kind': 'link',
        'label': 'Федерация',
        'url': url_for('regions.detail', region_id=region.id),
        'active': active_section is None and not showing_documents,
    }]

    for kind, key in FEDERATION_SIDEBAR_LAYOUT:
        if kind == 'category':
            category = fed_categories.get(key)
            if not category:
                continue
            category_url = url_for('regions.documents', region_id=region.id, category=category.id)
            category_active = (
                (active_category is not None and active_category.id == category.id)
                or (active_doc_section is not None and active_doc_section.category_id == category.id)
            )
            if not category.sections:
                # Категория без разделов — обычная ссылка-фильтр, без
                # шеврона и пустой раскрывашки «Разделов нет» (Направления
                # деятельности, Лицензирование и сертификация и т.п.).
                items.append({'kind': 'link', 'label': category.name, 'url': category_url, 'active': category_active})
                continue
            sections = [{
                'label': doc_section.name,
                'url': url_for('regions.documents', region_id=region.id, section=doc_section.id),
                'active': active_doc_section is not None and active_doc_section.id == doc_section.id,
            } for doc_section in category.sections]
            items.append({
                'kind': 'category',
                'label': category.name,
                'url': category_url,
                'active': category_active,
                'sections': sections,
            })
        else:
            items.append({
                'kind': 'link',
                'label': FUNCTIONAL_SECTION_LABELS[key],
                'url': url_for('regions.section', region_id=region.id, section=key),
                'active': active_section == key,
            })

    items.append({
        'kind': 'link',
        'label': 'Контакты',
        'url': url_for('regions.section', region_id=region.id, section='contacts'),
        'active': active_section == 'contacts',
    })
    items.append({
        'kind': 'link',
        'label': 'Все',
        'url': url_for('regions.documents', region_id=region.id),
        'active': active_section == 'all_documents',
    })
    return items


@bp.route('/')
def index():
    regional_federations = RegionalFederation.query.order_by(RegionalFederation.name).all()
    return render_template('regions/list.html', regional_federations=regional_federations)


@bp.route('/<int:region_id>')
def detail(region_id):
    region = RegionalFederation.query.get_or_404(region_id)
    return render_template('regions/detail.html', region=region, sidebar_items=_sidebar_items(region))


@bp.route('/<int:region_id>/<section>')
def section(region_id, section):
    if section not in SECTION_KEYS:
        abort(404)
    region = RegionalFederation.query.get_or_404(region_id)
    section_label = 'Клубы' if section == 'clubs' else FUNCTIONAL_SECTION_LABELS[section]

    region_clubs = []
    if section == 'clubs':
        region_clubs = Club.query.filter_by(region_id=region.id).order_by(Club.name).all()

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
        'regions/section.html', region=region, sidebar_items=_sidebar_items(region, active_section=section),
        section=section, section_label=section_label, team_athletes=team_athletes,
        region_clubs=region_clubs,
    )


@bp.route('/<int:region_id>/documents')
def documents(region_id):
    """Документы страницы конкретной федерации — категории/разделы общие
    для всех федераций (scope='федерация'), но сами документы у каждой
    федерации свои (Document.region_id). Устроена как «Соревнования →
    Нормативные документы» (routes/competitions.py: documents()), только
    с дополнительным фильтром по региону и без отдельной колонки
    категорий — она встроена в общее боковое меню «О федерации»
    (см. _sidebar_items())."""
    region = RegionalFederation.query.get_or_404(region_id)

    categories = (
        DocumentCategory.query.filter_by(scope='федерация')
        .order_by(DocumentCategory.name)
        .all()
    )
    category_names = [category.name for category in categories]
    section_ids = [doc_section.id for category in categories for doc_section in category.sections]

    selected_section_id = request.args.get('section', type=int)
    selected_section = DocumentSection.query.get(selected_section_id) if selected_section_id else None

    selected_category = None
    if not selected_section:
        selected_category_id = request.args.get('category', type=int)
        if selected_category_id:
            selected_category = next((c for c in categories if c.id == selected_category_id), None)

    query = (
        Document.query.filter_by(region_id=region.id)
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

    active_section = None if (selected_section or selected_category) else 'all_documents'

    return render_template(
        'regions/documents.html', region=region, documents=documents_,
        sidebar_items=_sidebar_items(
            region, active_section=active_section,
            active_category=selected_category, active_doc_section=selected_section,
        ),
        selected_section=selected_section, selected_category=selected_category,
    )
