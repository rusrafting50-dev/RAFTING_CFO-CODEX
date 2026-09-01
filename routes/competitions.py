"""Соревнования: календарный план, текущие, архив, страница соревнования."""
import json
import os
from datetime import date, datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import extract

from models import (
    CalendarPlanApplication, Competition, CompetitionApplication, CompetitionApplicationAthlete,
    CompetitionDocument, Document, DocumentCategory, DocumentSection,
    RegionalFederation, db,
)
from utils import safe_upload_filename

bp = Blueprint('competitions', __name__)

ALLOWED_LOGO_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}

BOAT_CLASSES = ['R4', 'R6']
DISCIPLINES = ['Спринт', 'Параллельный спринт', 'Слалом', 'Длинная гонка', 'Многоборье']
QUALIFICATIONS = ['МСМК', 'МС', 'КМС', 'I', 'II', 'III', 'б/р']
# Тот же список, что ВОЗРАСТНЫЕ_ГРУППЫ в COREZ (routes/заявка.py) — единый
# словарь значений на обеих сторонах.
AGE_GROUPS = [
    'Мужчины', 'Женщины',
    'Юниоры (до 26 лет)', 'Юниорки (до 26 лет)',
    'Юниоры (до 24 лет)', 'Юниорки (до 24 лет)',
    'Юниоры (до 20 лет)', 'Юниорки (до 20 лет)',
    'Юноши (до 16 лет)', 'Девушки (до 16 лет)',
]

# Карточки документов в блоке «Информация» на вкладке «О соревнованиях» —
# фиксированный набор, показывается всегда (даже если файл ещё не
# загружен), чтобы было видно, что именно нужно загрузить. doc_type
# должен быть среди COMPETITION_DOC_TYPE_CHOICES в routes/admin.py —
# ровно оттуда админ и загружает файл под конкретную карточку.
INFO_DOCUMENT_TYPES = [
    ('регламент', 'Регламент спортивных соревнований'),
    ('программа', 'Программа соревнований'),
    ('состав_гск', 'Состав главной судейской коллегии'),
    ('график_допуска', 'График прохождения комиссии по допуску'),
    ('расписание', 'Расписание тренировок'),
]

# Карточки документов в блоке «Документы соревнований» на той же
# вкладке — тот же приём, что INFO_DOCUMENT_TYPES.
COMPETITION_DOCUMENTS_TYPES = [
    ('справка_о_судьях', 'Справка о квалификации и составе судейской коллегии'),
    ('справка_о_субъектах', 'Справка о количестве регионов, принявших участие в соревнованиях'),
    ('протокол_совещания_гск', 'Протокол совещания ГСК с представителями команд'),
]

# Порядок и подписи дисциплин на вкладке "Результаты" (второй ряд меню).
# Список фиксированный — пункт появляется, только если для него реально
# пришли данные от COREZ (многоборье пересчитывается инкрементально по мере
# синхронизации остальных дисциплин, поэтому его пункт появляется вместе
# со спринтом, а не только в конце соревнования).
RESULT_DISCIPLINES = [
    ('результаты_спринт', 'Спринт'),
    ('результаты_пс', 'Параллельный спринт'),
    ('результаты_слалом', 'Слалом'),
    ('результаты_дг', 'Длинная гонка'),
    ('результаты_мб', 'Многоборье'),
]

# Вкладки уровня соревнования на «Официальные спортивные соревнования»
# (Competition.level) — «Клубы» здесь соответствует значению 'отделение'
# (см. модель: level — цфо/регион/отделение), а не отдельному значению
# 'клуб' — третий уровень структуры сайта («Местное отделение / Спортивный
# клуб», см. CLAUDE.md) в этом поле представлен только этим значением.
@bp.route('/')
def calendar():
    """Соревнования — календарный план текущего года (все уровни сразу,
    без деления по вкладкам ЦФО/Регионы/Клубы) + ссылки в архив трёх
    предыдущих лет."""
    year = date.today().year

    competitions = (
        Competition.query.filter(extract('year', Competition.start_date) == year)
        .order_by(Competition.start_date.asc())
        .all()
    )
    archive_years = [year - 1, year - 2, year - 3]

    # Ссылка «Положение о соревнованиях» во второй строке меню ведёт на
    # конкретную категорию страницы «Нормативные документы» (не на общий
    # список без фильтра) — тогда заголовок «Все документы» на той
    # странице меняется на название категории, как на странице
    # федерации. См. auth.py: rename_competition_regulations_category.
    regulations_category = DocumentCategory.query.filter_by(
        scope='соревнования', name='Положение о соревнованиях',
    ).first()

    calendar_applications = (
        CalendarPlanApplication.query.order_by(CalendarPlanApplication.created_at.desc()).all()
    )
    can_submit_calendar_application = (
        current_user.is_authenticated and current_user.role in ('region_rep', 'admin')
    )

    return render_template(
        'competitions/calendar.html', competitions=competitions, year=year,
        archive_years=archive_years, regulations_category=regulations_category,
        calendar_applications=calendar_applications,
        can_submit_calendar_application=can_submit_calendar_application,
    )


@bp.route('/current')
def current():
    competitions = (
        Competition.query.filter(Competition.status == 'идёт')
        .order_by(Competition.start_date.asc())
        .all()
    )
    return render_template(
        'competitions/list.html',
        competitions=competitions,
        title='Текущие соревнования',
    )


@bp.route('/archive')
def archive():
    year = request.args.get('year', type=int)

    query = Competition.query.filter(
        (Competition.status == 'завершены') | (Competition.end_date < date.today())
    )
    if year:
        query = query.filter(extract('year', Competition.start_date) == year)

    competitions = query.order_by(Competition.start_date.desc()).all()

    years = sorted(
        {c.start_date.year for c in Competition.query.all() if c.start_date},
        reverse=True,
    )

    return render_template(
        'competitions/list.html',
        competitions=competitions,
        title='Архив соревнований',
        archive=True,
        years=years,
        selected_year=year,
    )


@bp.route('/documents')
def documents():
    """Нормативные документы соревнований — список документов в шапке
    раздела «Соревнования», со своим боковым меню категорий
    (scope='соревнования').

    Документ появляется здесь, если при загрузке в админке ему назначили
    категорию из этого меню (Document.doc_category — совпадение по
    названию категории) и/или конкретный раздел внутри неё
    (Document.section_id) — раздел не обязателен, самой категории
    достаточно.

    Имя категории уникально только в пределах своего scope (см.
    DocumentCategory) — у страницы федерации (scope='федерация') есть
    категории с такими же названиями («Основополагающие документы» и
    т.п.), поэтому здесь дополнительно исключаются документы, у которых
    задан region_id (те принадлежат конкретной федерации, а не этой,
    общей для всего сайта, странице)."""
    categories = (
        DocumentCategory.query.filter_by(scope='соревнования')
        .order_by(DocumentCategory.sort_order, DocumentCategory.name)
        .all()
    )
    category_names = [category.name for category in categories]
    section_ids = [section.id for category in categories for section in category.sections]

    selected_section_id = request.args.get('section', type=int)
    selected_section = DocumentSection.query.get(selected_section_id) if selected_section_id else None

    selected_category = None
    if not selected_section:
        selected_category_id = request.args.get('category', type=int)
        if selected_category_id:
            selected_category = next((c for c in categories if c.id == selected_category_id), None)

    query = (
        Document.query.filter(Document.region_id.is_(None))
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

    return render_template(
        'competitions/documents.html', documents=documents_, categories=categories,
        selected_section=selected_section, selected_category=selected_category,
    )


# Первая строка меню на странице «Оборудование и снаряжение» — тот же
# приём, что EVENT_TYPE_FILTERS в routes/events.py.
EQUIPMENT_AUDIENCES = [
    ('спортсмены', 'Для спортсменов'),
    ('организаторы', 'Для организаторов соревнований'),
]
# Вторая строка меню зависит от выбранной аудитории — это разные
# DocumentCategory.scope (тот же приём, что 'соревнования'/'мероприятия').
EQUIPMENT_SCOPE_BY_AUDIENCE = {
    'спортсмены': 'оборудование_спортсмены',
    'организаторы': 'оборудование_организаторы',
}


@bp.route('/equipment')
def equipment():
    """Оборудование и снаряжение — третья вкладка раздела «Соревнования»
    (см. comp_tabs в competitions/_tabs.html). Сначала выбор аудитории
    (для спортсменов / для организаторов соревнований) — строка меню,
    затем на самой странице категории оборудования внутри выбранной
    аудитории (DocumentCategory, scope зависит от аудитории) выводятся
    как заголовки разделов, а не как отдельная строка меню-вкладок —
    под каждым заголовком сразу все документы этой категории."""
    audience = request.args.get('audience', 'спортсмены')
    if audience not in EQUIPMENT_SCOPE_BY_AUDIENCE:
        audience = 'спортсмены'
    scope = EQUIPMENT_SCOPE_BY_AUDIENCE[audience]

    categories = (
        DocumentCategory.query.filter_by(scope=scope)
        .order_by(DocumentCategory.sort_order, DocumentCategory.name)
        .all()
    )

    documents_by_category = {}
    for category in categories:
        # region_id.is_(None) — см. комментарий в documents() выше: имя
        # категории уникально только в пределах своего scope, а не глобально.
        documents_by_category[category.id] = (
            Document.query.filter_by(doc_category=category.name)
            .filter(Document.region_id.is_(None))
            .order_by(Document.uploaded_at.desc(), Document.title)
            .all()
        )

    return render_template(
        'competitions/equipment.html',
        audiences=EQUIPMENT_AUDIENCES, selected_audience=audience,
        categories=categories, documents_by_category=documents_by_category,
    )


def _federation_logo_lookup():
    """Логотип направляющей организации на «Команды» берём из логотипа
    региональной федерации с тем же названием — своего логотипа у заявки
    нет (см. events._federation_logo_lookup — та же логика)."""
    return {
        rf.name.strip().lower(): rf.logo_path
        for rf in RegionalFederation.query.filter(RegionalFederation.logo_path.isnot(None)).all()
    }


def _match_logo(lookup, organization_name):
    if not organization_name:
        return None
    return lookup.get(organization_name.strip().lower())


@bp.route('/<int:competition_id>')
def detail(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    applications = (
        CompetitionApplication.query.filter_by(competition_id=competition_id)
        .order_by(CompetitionApplication.created_at.desc())
        .all()
    )
    total_athletes = sum(len(a.athletes) for a in applications)
    can_submit_application = (
        current_user.is_authenticated and current_user.role in ('region_rep', 'admin')
    )
    logo_lookup = _federation_logo_lookup()
    application_logos = {
        a.id: a.logo_path or _match_logo(logo_lookup, a.org_name) for a in applications
    }
    documents = (
        CompetitionDocument.query.filter_by(competition_id=competition_id, is_published=True)
        .order_by(CompetitionDocument.doc_type)
        .all()
    )

    result_doc_types = {doc_type for doc_type, _ in RESULT_DISCIPLINES}

    documents_by_type = {}
    results_by_type = {}
    for document in documents:
        if document.results_data:
            # Протокол пришёл от COREZ как структурированные данные — строим таблицу.
            # Столбцы — объединение ключей всех строк с сохранением порядка появления.
            rows = json.loads(document.results_data)
            columns = []
            for row in rows:
                for key in row.keys():
                    if key not in columns:
                        columns.append(key)
            document.protocol_rows = rows
            document.protocol_columns = columns

        # результаты_* — на вкладку "Результаты" (сгруппированы по
        # дисциплине, внутри каждой может быть несколько отдельных таблиц,
        # например по группам R4/R6 × мужчины/женщины), остальные типы —
        # на "Протоколы".
        if document.doc_type in result_doc_types:
            results_by_type.setdefault(document.doc_type, []).append(document)
        else:
            documents_by_type.setdefault(document.doc_type, []).append(document)

    results_groups = [
        {'doc_type': doc_type, 'label': label, 'docs': results_by_type[doc_type]}
        for doc_type, label in RESULT_DISCIPLINES
        if doc_type in results_by_type
    ]

    info_documents = [
        {'doc_type': doc_type, 'label': label, 'docs': documents_by_type.get(doc_type, [])}
        for doc_type, label in INFO_DOCUMENT_TYPES
    ]
    competition_documents_docs = [
        {'doc_type': doc_type, 'label': label, 'docs': documents_by_type.get(doc_type, [])}
        for doc_type, label in COMPETITION_DOCUMENTS_TYPES
    ]

    return render_template(
        'competitions/detail.html',
        competition=competition,
        documents_by_type=documents_by_type,
        results_groups=results_groups,
        info_documents=info_documents,
        competition_documents_docs=competition_documents_docs,
        applications=applications, total_athletes=total_athletes,
        can_submit_application=can_submit_application, application_logos=application_logos,
    )


def _can_manage(application):
    return current_user.is_authenticated and (
        current_user.role == 'admin' or application.submitted_by_id == current_user.id
    )


@bp.route('/<int:competition_id>/applications/<int:application_id>/view')
def application_view(competition_id, application_id):
    competition = Competition.query.get_or_404(competition_id)
    application = CompetitionApplication.query.get_or_404(application_id)
    if application.competition_id != competition.id:
        abort(404)
    logo_path = application.logo_path or _match_logo(_federation_logo_lookup(), application.org_name)
    return render_template(
        'competitions/application_detail.html', competition=competition, application=application,
        can_manage=_can_manage(application), logo_path=logo_path,
    )


def _split_full_name(full_name):
    """Фамилия/имя/отчество отдельными полями в модели (совместимость со
    схемой COREZ), но в форме — одно поле «Фамилия, имя, отчество», как в
    заявке на семинар. Разбиваем по пробелам на 3 части — тот же приём,
    что использует сама форма COREZ (routes/заявка.py, `фио.split(None, 2)`)."""
    parts = full_name.split(None, 2)
    last_name = parts[0] if len(parts) > 0 else ''
    first_name = parts[1] if len(parts) > 1 else ''
    middle_name = parts[2] if len(parts) > 2 else ''
    return last_name, first_name, middle_name


def _apply_athletes(application_id, form):
    full_names = form.getlist('athlete_full_name[]')
    genders = form.getlist('athlete_gender[]')
    birth_dates = form.getlist('athlete_birth_date[]')
    qualifications = form.getlist('athlete_qualification[]')
    age_groups = form.getlist('athlete_age_group[]')
    order_numbers = form.getlist('athlete_order_number[]')
    insurance_numbers = form.getlist('athlete_insurance_number[]')

    for i, full_name in enumerate(full_names):
        full_name = full_name.strip()
        if not full_name:
            continue
        last_name, first_name, middle_name = _split_full_name(full_name)
        if not last_name:
            continue
        birth_date = None
        if i < len(birth_dates) and birth_dates[i]:
            try:
                birth_date = date.fromisoformat(birth_dates[i])
            except ValueError:
                birth_date = None
        db.session.add(CompetitionApplicationAthlete(
            application_id=application_id,
            last_name=last_name,
            first_name=first_name,
            middle_name=middle_name or None,
            gender=(genders[i].strip() or None) if i < len(genders) else None,
            birth_date=birth_date,
            qualification=(qualifications[i].strip() or None) if i < len(qualifications) else None,
            age_group=(age_groups[i].strip() or None) if i < len(age_groups) else None,
            order_number=(order_numbers[i].strip() or None) if i < len(order_numbers) else None,
            insurance_number=(insurance_numbers[i].strip() or None) if i < len(insurance_numbers) else None,
        ))


def _athletes_payload(application):
    if not application:
        return []
    return [
        {
            'full_name': ' '.join(filter(None, [a.last_name, a.first_name, a.middle_name])),
            'gender': a.gender,
            'birth_date': a.birth_date.isoformat() if a.birth_date else '',
            'qualification': a.qualification,
            'age_group': a.age_group,
            'order_number': a.order_number,
            'insurance_number': a.insurance_number,
        }
        for a in application.athletes
    ]


def _regional_federations():
    return RegionalFederation.query.order_by(RegionalFederation.name).all()


def _fill_application_fields(application, form):
    application.region = form.get('region', '').strip() or None
    application.team_name = form.get('team_name', '').strip() or None
    application.boat_class = form.get('boat_class', '').strip() or None
    application.discipline = form.get('discipline', '').strip() or None
    application.org_name = form.get('org_name', '').strip() or None
    application.org_leader_name = form.get('org_leader_name', '').strip() or None
    application.org_leader_position = form.get('org_leader_position', '').strip() or None
    application.org_leader_phone = form.get('org_leader_phone', '').strip() or None
    application.org_leader_email = form.get('org_leader_email', '').strip() or None
    application.coach_full_name = form.get('coach_full_name', '').strip() or None
    application.coach_phone = form.get('coach_phone', '').strip() or None
    application.coach_email = form.get('coach_email', '').strip() or None


def _allowed_logo(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_LOGO_EXTENSIONS


def _remove_logo_file(application):
    if not application.logo_path:
        return
    path = os.path.join(current_app.root_path, 'static', application.logo_path)
    if os.path.exists(path):
        os.remove(path)


def _apply_logo_upload(application, files):
    """Сохраняет новый логотип команды, если он выбран в форме — заменяя
    прежний, если был. Ошибка формата не прерывает сохранение остальной
    заявки, только логотип остаётся прежним."""
    file = files.get('logo')
    if not file or not file.filename:
        return True
    if not _allowed_logo(file.filename):
        flash('Логотип: допустимые форматы файлов — JPG, PNG, WEBP.', 'error')
        return False

    filename = safe_upload_filename(file.filename)
    unique_name = f"{datetime.utcnow():%Y%m%d%H%M%S}_{filename}"
    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, unique_name))

    _remove_logo_file(application)
    application.logo_path = f"uploads/{unique_name}"
    return True


@bp.route('/<int:competition_id>/applications/new', methods=['GET', 'POST'])
@login_required
def application_new(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if current_user.role not in ('region_rep', 'admin'):
        abort(403)

    if request.method == 'POST':
        full_names = request.form.getlist('athlete_full_name[]')
        if not any(name.strip() for name in full_names):
            flash('Добавьте хотя бы одного спортсмена.', 'error')
            return render_template(
                'competitions/application_form.html', competition=competition, application=None,
                existing_athletes=[], regional_federations=_regional_federations(),
                boat_classes=BOAT_CLASSES, disciplines=DISCIPLINES,
                qualifications=QUALIFICATIONS, age_groups=AGE_GROUPS,
            )

        application = CompetitionApplication(
            competition_id=competition.id, submitted_by_id=current_user.id, origin='site',
        )
        _fill_application_fields(application, request.form)
        _apply_logo_upload(application, request.files)
        db.session.add(application)
        db.session.flush()
        _apply_athletes(application.id, request.form)
        db.session.commit()

        flash('Заявка сохранена.', 'success')
        return redirect(url_for('competitions.detail', competition_id=competition.id) + '#tab-entries')

    return render_template(
        'competitions/application_form.html', competition=competition, application=None,
        existing_athletes=[], regional_federations=_regional_federations(),
        boat_classes=BOAT_CLASSES, disciplines=DISCIPLINES,
        qualifications=QUALIFICATIONS, age_groups=AGE_GROUPS,
    )


@bp.route('/<int:competition_id>/applications/<int:application_id>/edit', methods=['GET', 'POST'])
@login_required
def application_edit(competition_id, application_id):
    competition = Competition.query.get_or_404(competition_id)
    application = CompetitionApplication.query.get_or_404(application_id)
    if application.competition_id != competition.id:
        abort(404)
    if not _can_manage(application):
        abort(403)

    if request.method == 'POST':
        full_names = request.form.getlist('athlete_full_name[]')
        if not any(name.strip() for name in full_names):
            flash('Добавьте хотя бы одного спортсмена.', 'error')
            return render_template(
                'competitions/application_form.html', competition=competition, application=application,
                existing_athletes=_athletes_payload(application), regional_federations=_regional_federations(),
                boat_classes=BOAT_CLASSES, disciplines=DISCIPLINES,
                qualifications=QUALIFICATIONS, age_groups=AGE_GROUPS,
            )

        _fill_application_fields(application, request.form)
        _apply_logo_upload(application, request.files)
        application.updated_at = datetime.utcnow()
        CompetitionApplicationAthlete.query.filter_by(application_id=application.id).delete()
        _apply_athletes(application.id, request.form)
        db.session.commit()

        flash('Заявка обновлена.', 'success')
        return redirect(url_for('competitions.detail', competition_id=competition.id) + '#tab-entries')

    return render_template(
        'competitions/application_form.html', competition=competition, application=application,
        existing_athletes=_athletes_payload(application), regional_federations=_regional_federations(),
        boat_classes=BOAT_CLASSES, disciplines=DISCIPLINES,
        qualifications=QUALIFICATIONS, age_groups=AGE_GROUPS,
    )


@bp.route('/<int:competition_id>/applications/<int:application_id>/delete', methods=['POST'])
@login_required
def application_delete(competition_id, application_id):
    application = CompetitionApplication.query.get_or_404(application_id)
    if application.competition_id != competition_id:
        abort(404)
    if not _can_manage(application):
        abort(403)

    _remove_logo_file(application)
    db.session.delete(application)
    db.session.commit()
    flash('Заявка удалена.', 'success')
    return redirect(url_for('competitions.detail', competition_id=competition_id) + '#tab-entries')


# ---------- Заявки на включение соревнования в ЕКП (вкладка «Формирование
# календарного плана») ----------

# Роли предлагаемого состава ГСК и технического делегата — у каждой один
# и тот же набор полей (ФИО, квалификация, субъект, город), см.
# CalendarPlanApplication в models.py.
CALENDAR_APPLICATION_ROLES = [
    ('chief_judge', 'Главный судья'),
    ('chief_secretary', 'Главный секретарь'),
    ('deputy_judge', 'Заместитель главного судьи по судейству'),
    ('deputy_organizer', 'Заместитель главного судьи по организационным вопросам'),
    ('distance_chief', 'Начальник дистанции'),
    ('tech_delegate', 'Технический делегат'),
]


def _fill_calendar_application_fields(application, form):
    application.status = form.get('status', '').strip() or None
    application.program_types = form.get('program_types', '').strip() or None
    application.location_subject = form.get('location_subject', '').strip() or None
    application.location_details = form.get('location_details', '').strip() or None
    application.organizations = form.get('organizations', '').strip() or None
    application.program_schedule = form.get('program_schedule', '').strip() or None

    application.start_date = None
    start_date = form.get('start_date')
    if start_date:
        try:
            application.start_date = date.fromisoformat(start_date)
        except ValueError:
            pass

    application.end_date = None
    end_date = form.get('end_date')
    if end_date:
        try:
            application.end_date = date.fromisoformat(end_date)
        except ValueError:
            pass

    for role, _label in CALENDAR_APPLICATION_ROLES:
        setattr(application, f'{role}_name', form.get(f'{role}_name', '').strip() or None)
        setattr(application, f'{role}_qualification', form.get(f'{role}_qualification', '').strip() or None)
        setattr(application, f'{role}_region', form.get(f'{role}_region', '').strip() or None)
        setattr(application, f'{role}_city', form.get(f'{role}_city', '').strip() or None)

    application.federation_contact_name = form.get('federation_contact_name', '').strip() or None
    application.federation_contact_phone = form.get('federation_contact_phone', '').strip() or None
    application.federation_contact_email = form.get('federation_contact_email', '').strip() or None
    application.chief_judge_contact_name = form.get('chief_judge_contact_name', '').strip() or None
    application.chief_judge_contact_phone = form.get('chief_judge_contact_phone', '').strip() or None
    application.chief_judge_contact_email = form.get('chief_judge_contact_email', '').strip() or None


@bp.route('/calendar-applications/new', methods=['GET', 'POST'])
@login_required
def calendar_application_new():
    if current_user.role not in ('region_rep', 'admin'):
        abort(403)

    if request.method == 'POST':
        application = CalendarPlanApplication(submitted_by_id=current_user.id)
        _fill_calendar_application_fields(application, request.form)
        db.session.add(application)
        db.session.commit()
        flash('Заявка сохранена.', 'success')
        return redirect(url_for('competitions.calendar') + '#tab-forming')

    return render_template(
        'competitions/calendar_application_form.html', application=None,
        roles=CALENDAR_APPLICATION_ROLES, qualifications=QUALIFICATIONS,
    )


@bp.route('/calendar-applications/<int:application_id>/edit', methods=['GET', 'POST'])
@login_required
def calendar_application_edit(application_id):
    application = CalendarPlanApplication.query.get_or_404(application_id)
    if not _can_manage(application):
        abort(403)

    if request.method == 'POST':
        _fill_calendar_application_fields(application, request.form)
        db.session.commit()
        flash('Заявка обновлена.', 'success')
        return redirect(url_for('competitions.calendar') + '#tab-forming')

    return render_template(
        'competitions/calendar_application_form.html', application=application,
        roles=CALENDAR_APPLICATION_ROLES, qualifications=QUALIFICATIONS,
    )


@bp.route('/calendar-applications/<int:application_id>')
def calendar_application_view(application_id):
    application = CalendarPlanApplication.query.get_or_404(application_id)
    return render_template(
        'competitions/calendar_application_detail.html', application=application,
        roles=CALENDAR_APPLICATION_ROLES, can_manage=_can_manage(application),
    )


@bp.route('/calendar-applications/<int:application_id>/delete', methods=['POST'])
@login_required
def calendar_application_delete(application_id):
    application = CalendarPlanApplication.query.get_or_404(application_id)
    if not _can_manage(application):
        abort(403)

    db.session.delete(application)
    db.session.commit()
    flash('Заявка удалена.', 'success')
    return redirect(url_for('competitions.calendar') + '#tab-forming')
