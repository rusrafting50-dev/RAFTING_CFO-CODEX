"""Региональные федерации субъектов ЦФО."""
from flask import Blueprint, abort, render_template, request, url_for

from models import (
    Athlete, Club, Council, CouncilCategory, CouncilMember, CouncilPage, Document, DocumentCategory,
    DocumentSection, LocalFederation, News, RegionalFederation, db,
)

bp = Blueprint('regions', __name__)

# «Функциональные» разделы бокового меню «О федерации» — со своими
# реальными данными (в отличие от категорий документов ниже). goals —
# свободный текст, RegionalFederation.goals_text (поле «Направления
# деятельности» в админке); для leadership/calendar пока нет своей
# модели данных — раздел открывается с заглушкой «материалы пока не
# добавлены», как и на других страницах сайта, где источник данных ещё
# не подключён; team — реальные данные из REGTEAM_RAFTING (см. section()
# ниже), contacts — поля RegionalFederation.
#
# 'clubs' сюда не входит: этот раздел убран из бокового меню «О
# федерации» по просьбе федерации, но сама страница остаётся рабочей —
# на неё по-прежнему ведёт пункт «Клубы» в шапке сайта и подвале
# (base.html), поэтому раздел/маршрут не удаляется, а только перестаёт
# быть пунктом этого меню.
FUNCTIONAL_SECTIONS = [
    ('goals', 'Направления деятельности'),
    ('leadership', 'Руководство'),
    ('local_federations', 'Местные спортивные федерации'),
    ('councils', 'Коллегии и советы'),
    ('calendar', 'Календарный план'),
    ('team', 'Сборная команда'),
    ('contacts', 'Контакты'),
]
FUNCTIONAL_SECTION_LABELS = dict(FUNCTIONAL_SECTIONS)

# Разделы собственного бокового меню «Сборная команда», помимо «Состав»
# (см. TEAM_MENU_STUB_LABELS/_team_sidebar_items() ниже) — вынесены сюда
# же, чтобы попасть в SECTION_KEYS вместе с FUNCTIONAL_SECTIONS/'clubs'.
# 'team_coaches' — реальные данные из REGTEAM_RAFTING (см. section()),
# 'team_calendar'/'team_news'/'team_media' пока остаются заглушками
# «материалы пока не добавлены» — источник данных для них ещё не
# подключён.
TEAM_MENU_STUB_SECTIONS = [
    ('team_coaches', 'Тренеры'),
    ('team_calendar', 'Календарь'),
    ('team_news', 'Новости'),
    ('team_media', 'Медиа'),
]
TEAM_MENU_STUB_LABELS = dict(TEAM_MENU_STUB_SECTIONS)

SECTION_KEYS = {key for key, _ in FUNCTIONAL_SECTIONS} | {'clubs'} | set(TEAM_MENU_STUB_LABELS)

# Расположение пунктов бокового меню «О федерации» между «Федерация»
# вверху и «Контакты» внизу (последней) — чередование категорий
# документов страницы федерации (scope='федерация', сколько их сейчас
# есть — см. auth.py: FEDERATION_DOCUMENT_TAXONOMY) с функциональными разделами из
# FUNCTIONAL_SECTIONS в заданных федерацией местах. Сама категория,
# оказавшаяся в очередном слоте 'category', и порядок категорий между
# собой — определяются DocumentCategory.sort_order (задаётся в панели
# управления кнопками ▲/▼, admin/document_taxonomy.html), а не этим
# списком — здесь зафиксированы только места функциональных разделов
# относительно категорий (четвёртая категория в списке сейчас —
# «Положение о межмуниципальных...», её слот идёт последним перед
# «Сборная команда»). 'goals' — первым пунктом, до всех категорий
# документов, как раньше был «Цели и задачи».
FEDERATION_SIDEBAR_LAYOUT = [
    ('functional', 'goals'),
    'category', ('functional', 'leadership'),
    ('functional', 'local_federations'),
    ('functional', 'councils'),
    'category', 'category', ('functional', 'calendar'),
    'category', ('functional', 'team'),
]

# Раздел «Сборная команда»: верхняя строка — пол (мужские/женские),
# вторая — возрастная категория внутри выбранного пола. Значения
# категорий сравниваются с Athlete.national_team — REGTEAM_RAFTING
# присылает сюда свою возрастную категорию (age_category, справочник
# references.AGE_CATEGORIES: Мужчины/Женщины/Юниоры/Юниорки/Юноши/
# Девушки — без разбивки по годам, там её нет), сайт данные не
# редактирует, только показывает. Пол сам по себе отдельным полем не
# хранится — выводится из того, какой из двух списков содержит
# категорию спортсмена.
TEAM_GENDERS = [
    ('мужские', 'Мужские'),
    ('женские', 'Женские'),
]
TEAM_CATEGORIES_BY_GENDER = {
    'мужские': ['Мужчины', 'Юниоры', 'Юноши'],
    'женские': ['Женщины', 'Юниорки', 'Девушки'],
}
TEAM_GENDER_BY_CATEGORY = {
    category.lower(): gender
    for gender, categories in TEAM_CATEGORIES_BY_GENDER.items()
    for category in categories
}

# Собственное боковое меню раздела «Сборная команда» — полностью заменяет
# общее меню «О федерации» (regions/_sidebar.html/_sidebar_items()) на
# странице сборной, странице отдельного спортсмена и на страницах-
# заглушках TEAM_MENU_STUB_SECTIONS (см. выше).
TEAM_MENU_SECTION_KEYS = {'team'} | set(TEAM_MENU_STUB_LABELS)


def _clubs_by_name():
    """Клубы по названию в нижнем регистре — Athlete.organization
    сопоставляется с Club.name строкой, а не внешним ключом (REGTEAM_RAFTING
    не знает внутренних id сайта). Сравнение без учёта регистра — в
    Python, не в SQL: LOWER() в SQLite не работает с кириллицей."""
    return {c.name.strip().lower(): c for c in Club.query.all()}


def _team_roster(region, category, clubs_by_name):
    """Спортсмены сборной команды региона в заданной возрастной категории
    (Athlete.national_team), отсортированные по алфавиту — общий список
    для сетки карточек (section(), 'team') и бокового списка на странице
    отдельного спортсмена (team_athlete())."""
    if not region.subject_name or not category:
        return []
    subject_name = region.subject_name.strip().lower()
    category_lower = category.strip().lower()
    return sorted(
        (
            a for a in Athlete.query.filter(Athlete.is_active.is_(True)).all()
            if a.territory and a.territory.strip().lower() == subject_name
            and a.organization and a.organization.strip().lower() in clubs_by_name
            and a.national_team and a.national_team.strip().lower() == category_lower
        ),
        key=lambda a: a.full_name,
    )


# Тренеры, числящиеся в REGTEAM_RAFTING не за клубом, а напрямую за
# федерацией — направляющая организация в этом случае равна этой строке
# (точное совпадение без учёта регистра), а не названию клуба, и на
# карточке вместо логотипа клуба показывается логотип самой федерации
# (RegionalFederation.logo_path) — см. _team_coaches()/section().
FEDERATION_ORG_LABEL = 'МОСФ'


def _team_coaches(region, clubs_by_name):
    """Тренеры сборной региона — та же логика отбора, что _team_roster()
    (совпадение territory с субъектом РФ федерации, is_active — в
    текущем составе), но без деления по полу/возрастной категории (на
    странице «Тренеры» его нет, см. regions/section.html) и с
    допущением направляющей организации FEDERATION_ORG_LABEL в
    придачу к настоящим клубам — тренеры федерации к клубу не
    привязаны."""
    if not region.subject_name:
        return []
    subject_name = region.subject_name.strip().lower()
    federation_label = FEDERATION_ORG_LABEL.lower()
    return sorted(
        (
            a for a in Athlete.query.filter(Athlete.is_active.is_(True), Athlete.role == 'тренер').all()
            if a.territory and a.territory.strip().lower() == subject_name
            and a.organization and (
                a.organization.strip().lower() in clubs_by_name
                or a.organization.strip().lower() == federation_label
            )
        ),
        key=lambda a: a.full_name,
    )


def _coach_logo_path(region, coach, clubs_by_name):
    """Бейдж-логотип на карточке тренера — логотип его клуба, а если
    направляющая организация не клуб, а сама федерация
    (FEDERATION_ORG_LABEL, «МОСФ») — логотип региональной федерации."""
    club = clubs_by_name.get((coach.organization or '').strip().lower())
    return club.logo_path if club else region.logo_path


def _category_sidebar_item(region, category, active_category, active_doc_section):
    """Один пункт меню для категории документов страницы федерации —
    раскрывающийся, если у категории есть разделы (kind='category'), или
    обычная ссылка-фильтр без шеврона и пустой раскрывашки «Разделов
    нет», если разделов нет (kind='link')."""
    url = url_for('regions.documents', region_id=region.id, category=category.id)
    active = (
        (active_category is not None and active_category.id == category.id)
        or (active_doc_section is not None and active_doc_section.category_id == category.id)
    )
    if not category.sections:
        return {'kind': 'link', 'label': category.name, 'url': url, 'active': active}
    sections = [{
        'label': doc_section.name,
        'url': url_for('regions.documents', region_id=region.id, section=doc_section.id),
        'active': active_doc_section is not None and active_doc_section.id == doc_section.id,
    } for doc_section in category.sections]
    return {'kind': 'category', 'label': category.name, 'url': url, 'active': active, 'sections': sections}


def _team_sidebar_items(region, active_key, roster=None, current_athlete_id=None, team_gender=None, team_category=None):
    """Боковое меню раздела «Сборная команда»: Состав/Тренеры/Календарь/
    Новости/Медиа — используется вместо _sidebar_items() (общего меню «О
    федерации») на regions/section.html при section в TEAM_MENU_SECTION_KEYS
    и на regions/team_athlete.html.

    «Состав» раскрывается (kind='category', тот же приём, что категории
    документов в _sidebar_items()) с разделами — ФИО каждого спортсмена
    того же состава со ссылкой на его страницу — только когда передан
    roster (это происходит исключительно на странице отдельного
    спортсмена, team_athlete()); на самой странице «Сборная команда» и на
    страницах-заглушках roster не передаётся, и «Состав» — обычная ссылка
    без раскрывашки: этим и достигается требование «при переходе на
    другую страницу разделы ФИО исчезают»."""
    roster_url = url_for(
        'regions.section', region_id=region.id, section='team',
        gender=team_gender, category=team_category,
    )
    if roster:
        sections = [{
            'label': member.full_name,
            'url': url_for('regions.team_athlete', region_id=region.id, athlete_id=member.id),
            'active': member.id == current_athlete_id,
        } for member in roster]
        items = [{'kind': 'category', 'label': 'Состав', 'url': roster_url, 'active': active_key == 'team', 'sections': sections}]
    else:
        items = [{'kind': 'link', 'label': 'Состав', 'url': roster_url, 'active': active_key == 'team'}]

    for key, label in TEAM_MENU_STUB_SECTIONS:
        items.append({
            'kind': 'link',
            'label': label,
            'url': url_for('regions.section', region_id=region.id, section=key),
            'active': active_key == key,
        })
    return items


def _sidebar_items(region, active_section=None, active_category=None, active_doc_section=None):
    """Пункты бокового меню «О федерации»: «Федерация» вверху (ссылка на
    обзорную страницу), затем FEDERATION_SIDEBAR_LAYOUT (с «Документы» —
    сбрасывает фильтр документов — сразу после «Коллегии и советы»),
    затем «Контакты» последним пунктом.

    Категории документов (scope='федерация') с разделами рендерятся как
    раскрывающиеся пункты со своими разделами внутри (kind='category') —
    тот же приём, что doc-category-panel на «Соревнования → Нормативные
    документы»; категории без единого раздела (например, «Направления
    деятельности») — обычная ссылка-фильтр, без шеврона и пустой
    раскрывашки, как и функциональные разделы и «Контакты» (kind='link').
    Текущий пункт выводится не строкой списка, а плашкой-заголовком
    (см. regions/_sidebar.html)."""
    ordered_categories = iter(
        DocumentCategory.query.filter_by(scope='федерация')
        .order_by(DocumentCategory.sort_order, DocumentCategory.name)
        .all()
    )
    showing_documents = active_category is not None or active_doc_section is not None or active_section == 'all_documents'

    items = [{
        'kind': 'link',
        'label': 'Федерация',
        'url': url_for('regions.detail', region_id=region.id),
        'active': active_section is None and not showing_documents,
    }]

    for slot in FEDERATION_SIDEBAR_LAYOUT:
        if slot == 'category':
            category = next(ordered_categories, None)
            if category:
                items.append(_category_sidebar_item(region, category, active_category, active_doc_section))
        else:
            _, key = slot
            items.append({
                'kind': 'link',
                'label': FUNCTIONAL_SECTION_LABELS[key],
                'url': url_for('regions.section', region_id=region.id, section=key),
                'active': active_section == key,
            })
            if key == 'councils':
                items.append({
                    'kind': 'link',
                    'label': 'Документы',
                    'url': url_for('regions.documents', region_id=region.id),
                    'active': active_section == 'all_documents',
                })

    # Категории сверх заранее расставленных слотов (например, новая
    # категория, добавленная в панели управления) — довешиваются в конец,
    # перед функциональными разделами, а не пропадают из меню молча.
    for category in ordered_categories:
        items.append(_category_sidebar_item(region, category, active_category, active_doc_section))

    items.append({
        'kind': 'link',
        'label': 'Контакты',
        'url': url_for('regions.section', region_id=region.id, section='contacts'),
        'active': active_section == 'contacts',
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
    if section == 'clubs':
        section_label = 'Клубы'
    elif section in TEAM_MENU_STUB_LABELS:
        section_label = TEAM_MENU_STUB_LABELS[section]
    else:
        section_label = FUNCTIONAL_SECTION_LABELS[section]

    region_clubs = []
    if section == 'clubs':
        region_clubs = Club.query.filter_by(region_id=region.id).order_by(Club.name).all()

    region_local_federations = []
    if section == 'local_federations':
        region_local_federations = (
            LocalFederation.query.filter_by(region_id=region.id).order_by(LocalFederation.name).all()
        )

    team_roster = []
    team_gender = None
    team_category = None
    if section == 'team':
        team_gender = request.args.get('gender')
        if team_gender not in TEAM_CATEGORIES_BY_GENDER:
            team_gender = 'мужские'
        categories = TEAM_CATEGORIES_BY_GENDER[team_gender]
        team_category = request.args.get('category')
        if team_category not in categories:
            team_category = categories[0]

        clubs_by_name = _clubs_by_name()
        team_roster = [
            {'athlete': athlete, 'club': clubs_by_name.get((athlete.organization or '').strip().lower())}
            for athlete in _team_roster(region, team_category, clubs_by_name)
        ]

    team_coaches = []
    if section == 'team_coaches':
        clubs_by_name = _clubs_by_name()
        team_coaches = [{
            'athlete': coach,
            'logo_path': _coach_logo_path(region, coach, clubs_by_name),
            'gender': TEAM_GENDER_BY_CATEGORY.get((coach.national_team or '').strip().lower(), 'мужские'),
        } for coach in _team_coaches(region, clubs_by_name)]

    council_categories = []
    active_council_category_id = None
    if section == 'councils':
        council_categories = CouncilCategory.query.order_by(CouncilCategory.sort_order, CouncilCategory.name).all()
        active_council_category_id = request.args.get('category', type=int)
        if active_council_category_id not in {c.id for c in council_categories}:
            active_council_category_id = council_categories[0].id if council_categories else None

    if section in TEAM_MENU_SECTION_KEYS:
        sidebar_items = _team_sidebar_items(region, active_key=section, team_gender=team_gender, team_category=team_category)
    else:
        sidebar_items = _sidebar_items(region, active_section=section)

    return render_template(
        'regions/section.html', region=region, sidebar_items=sidebar_items,
        section=section, section_label=section_label, region_clubs=region_clubs,
        team_roster=team_roster, team_gender=team_gender, team_category=team_category,
        team_genders=TEAM_GENDERS, team_categories=TEAM_CATEGORIES_BY_GENDER.get(team_gender, []),
        team_coaches=team_coaches, region_local_federations=region_local_federations,
        council_categories=council_categories, active_council_category_id=active_council_category_id,
    )


def _councils_sidebar_items(region, active_council_id=None):
    """Боковое меню страницы конкретной коллегии/совета — полностью
    заменяет общее меню «О федерации» (тот же приём, что
    _team_sidebar_items()): только категории (CouncilCategory) с
    раскрывающимся списком советов внутри (kind='category', как
    категории документов в _sidebar_items()), без «Федерация»/
    «Руководство»/... Название категории само по себе ведёт на список
    «Коллегии и советы» этой федерации, отфильтрованный по ней."""
    items = []
    for category in CouncilCategory.query.order_by(CouncilCategory.sort_order, CouncilCategory.name).all():
        sections = [{
            'label': council.name,
            'url': url_for('regions.council_detail', region_id=region.id, council_id=council.id),
            'active': council.id == active_council_id,
        } for council in category.councils]
        items.append({
            'kind': 'category',
            'label': category.name,
            'url': url_for('regions.section', region_id=region.id, section='councils', category=category.id),
            'active': any(s['active'] for s in sections),
            'sections': sections,
        })
    return items


@bp.route('/<int:region_id>/councils/<int:council_id>')
def council_detail(region_id, council_id):
    """Страница конкретной коллегии/совета федерации — вкладка «Общая
    информация»: текст из админки (CouncilPage) для этой пары (совет,
    федерация) и новости, отмеченные этим советом (News.council_id)."""
    region = RegionalFederation.query.get_or_404(region_id)
    council = Council.query.get_or_404(council_id)
    page = CouncilPage.query.filter_by(region_id=region.id, council_id=council.id).first()
    tagged_news = (
        News.query.filter_by(council_id=council.id, is_published=True)
        .order_by(News.published_at.desc())
        .all()
    )
    return render_template(
        'regions/council_detail.html', region=region, council=council, page=page, tagged_news=tagged_news,
        sidebar_items=_councils_sidebar_items(region, active_council_id=council.id),
    )


@bp.route('/<int:region_id>/councils/<int:council_id>/members')
def council_members(region_id, council_id):
    """Вкладка «Состав» страницы коллегии/совета — руководитель(и)
    (CouncilMember.is_chairman) баннером с фото, остальной состав —
    списком ФИО/должность в том же виде, что кнопки советов на списке
    «Коллегии и советы» (regions/_council_button.html)."""
    region = RegionalFederation.query.get_or_404(region_id)
    council = Council.query.get_or_404(council_id)
    members = (
        CouncilMember.query.filter_by(region_id=region.id, council_id=council.id)
        .order_by(CouncilMember.sort_order, CouncilMember.full_name)
        .all()
    )
    chairmen = [m for m in members if m.is_chairman]
    other_members = [m for m in members if not m.is_chairman]
    return render_template(
        'regions/council_members.html', region=region, council=council,
        chairmen=chairmen, other_members=other_members,
        sidebar_items=_councils_sidebar_items(region, active_council_id=council.id),
    )


@bp.route('/<int:region_id>/team/<int:athlete_id>')
def team_athlete(region_id, athlete_id):
    """Страница отдельного спортсмена сборной команды федерации — справа
    боковое меню «Сборная команда» (см. _team_sidebar_items()), с
    раскрытым списком остального состава той же возрастной категории под
    пунктом «Состав» (regions/team_athlete.html)."""
    region = RegionalFederation.query.get_or_404(region_id)
    athlete = Athlete.query.get_or_404(athlete_id)

    clubs_by_name = _clubs_by_name()
    club = clubs_by_name.get((athlete.organization or '').strip().lower())
    category = athlete.national_team.strip() if athlete.national_team else None
    gender = TEAM_GENDER_BY_CATEGORY.get(category.lower()) if category else None
    roster = _team_roster(region, category, clubs_by_name)

    # Меню пола/категории — то же, что на странице сборной команды
    # (section(), 'team'), сюда попадает как gender/category самого
    # спортсмена (для подсветки активного пункта), так что если
    # категория не распознана (не входит ни в один из списков
    # TEAM_CATEGORIES_BY_GENDER), меню всё равно строится — по умолчанию
    # 'мужские', как и на странице сборной команды.
    menu_gender = gender or 'мужские'

    sidebar_items = _team_sidebar_items(
        region, active_key='team', roster=roster, current_athlete_id=athlete.id,
        team_gender=menu_gender, team_category=category,
    )

    return render_template(
        'regions/team_athlete.html', region=region, athlete=athlete, club=club,
        roster=roster, gender=gender, category=category, sidebar_items=sidebar_items,
        team_genders=TEAM_GENDERS, team_categories=TEAM_CATEGORIES_BY_GENDER.get(menu_gender, []),
        menu_gender=menu_gender,
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
        .order_by(DocumentCategory.sort_order, DocumentCategory.name)
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
