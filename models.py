"""Модели базы данных SQLAlchemy.

База данных `shared.db` общая для сайта и трёх внутренних проектов
(COREZ, REGTEAM_RAFTING, SPORTS_REFEREE). Сайт данные только читает,
за исключением новостей, документов и состава органов федерации,
которые редактируются вручную через админку.
"""
from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class News(db.Model):
    """Новости сайта."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    # Краткое описание для карточек новостей (title -> description -> дата).
    # Если не заполнено, шаблоны показывают обрезанный content.
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # см. NewsCategory — список редактируется в админке
    level = db.Column(db.String(50))  # см. NewsLevel — список редактируется в админке
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    image_path = db.Column(db.String(500))
    # Подпись под фото на странице новости ("Автор фото: X, Организация").
    photo_author = db.Column(db.String(255))
    organization = db.Column(db.String(255))
    # Тег «эта новость про такой-то комитет» — новостные карточки на
    # странице конкретной коллегии/совета региональной федерации
    # (routes/regions.py: council_detail(), вкладка «Общая информация»).
    council_id = db.Column(db.Integer, db.ForeignKey('council.id'))
    # Новость конкретной региональной федерации — задаётся вручную в
    # админке (в отличие от Competition/Athlete/Referee/Event, у новости
    # нет внешнего источника с субъектом РФ для сопоставления). Помимо
    # общего списка новостей сайта (main.news, region_id не участвует в
    # фильтре), выводится ещё и на странице «Новости» этой федерации
    # (routes/regions.py: section(), раздел 'news').
    region_id = db.Column(db.Integer, db.ForeignKey('regional_federation.id'))

    author = db.relationship('User', backref='news_items')
    council = db.relationship('Council', backref='tagged_news')
    region = db.relationship('RegionalFederation', backref='news_items')


class NewsImage(db.Model):
    """Дополнительные фото новости — слайдер внизу страницы новости
    (помимо основного фото News.image_path, которое идёт в шапку страницы
    и на карточки в списке)."""

    id = db.Column(db.Integer, primary_key=True)
    news_id = db.Column(db.Integer, db.ForeignKey('news.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)

    news = db.relationship('News', backref=db.backref('gallery_images', cascade='all, delete-orphan'))


class NewsCategory(db.Model):
    """Список допустимых категорий новостей — редактируется в админке.

    Значения 'федерация', 'соревнование', 'регион', 'мероприятие'
    используются в коде (routes/main.py: OFFICIAL_NEWS_CATEGORY,
    NEWS_MENU) — их удаление/переименование не сломает существующие
    новости, но отвяжет их от колонки "Официально"/меню фильтра.
    """

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)


class NewsLevel(db.Model):
    """Список допустимых уровней новостей — редактируется в админке."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)


class Competition(db.Model):
    """Соревнования — поступают из проекта COREZ."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    comp_type = db.Column(db.String(50))  # официальные спортивные / физкультурные
    level = db.Column(db.String(50))  # цфо / регион / отделение
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    location = db.Column(db.String(255))
    # Субъект РФ (напр. "Тверская область") — отдельно от location
    # (свободный адрес места проведения): используется, чтобы показать
    # соревнование ещё и на календарном плане той региональной федерации,
    # чей RegionalFederation.subject_name совпадает (см. routes/regions.py:
    # section(), сравнение без учёта регистра — тот же приём, что для
    # Athlete/Referee.territory).
    subject_name = db.Column(db.String(255))
    status = db.Column(db.String(50))  # анонс / идёт / завершены
    source_id = db.Column(db.Integer)  # ID в базе COREZ
    # Из карточки соревнования COREZ — для отображения в том же виде на сайте.
    age_group = db.Column(db.String(255))  # возрастная группа (напр. "Мужчины, женщины")
    boat_class = db.Column(db.String(20))  # класс судна: R4 / R6 / R4/R6
    head_judge = db.Column(db.String(255))  # гл. судья соревнований
    registration_number = db.Column(db.String(100))  # № ЕКП
    logo_path = db.Column(db.String(500))  # логотип соревнования (относительно static/)
    # Логотип загружен вручную в панели управления (routes/admin.py:
    # competition_logo_upload) — тогда синхронизация из COREZ его не
    # перезаписывает (см. routes/api.py: sync_competitions), иначе
    # загруженный логотип пропадал бы при следующей же синхронизации.
    logo_is_manual = db.Column(db.Boolean, nullable=False, default=False)
    disciplines = db.Column(db.String(255))  # виды программы (напр. "Слалом, Спринт")

    documents = db.relationship(
        'CompetitionDocument', backref='competition',
        lazy=True, cascade='all, delete-orphan',
    )


class CompetitionDocument(db.Model):
    """Документы соревнования (положение, регламент, протоколы и т.д.)."""

    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey('competition.id'), nullable=False)
    doc_type = db.Column(db.String(50))  # положение / регламент / состав_гск / расписание / заявки / стартовый_протокол / протокол_результатов / ...
    title = db.Column(db.String(255))
    file_path = db.Column(db.String(500))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    # JSON-список строк протокола (только для стартовый_протокол / протокол_результатов),
    # заполняется через API синхронизации, если COREZ присылает структурированные данные,
    # а не только файл
    results_data = db.Column(db.Text)
    # Публикация на сайте управляется отдельно от факта загрузки — можно
    # загрузить документ заранее и опубликовать позже галочкой в админке.
    # По умолчанию True, чтобы уже загруженные документы не пропали с
    # сайта при обновлении на существующей базе.
    is_published = db.Column(db.Boolean, default=True, nullable=False)


class Athlete(db.Model):
    """Спортсмены и тренеры сборной — поступают из REGTEAM_RAFTING.

    organization — направляющая организация (клуб/школа), по названию
    сопоставляется с Club.name для разделов «Тренеры»/«Спортсмены» на
    странице клуба. territory приходит от REGTEAM_RAFTING уже на уровне
    субъекта РФ (не внутреннего района инстанса-источника) и по названию
    сопоставляется с RegionalFederation.subject_name для раздела
    «Сборная команда» на странице федерации — то же соответствие, что
    Club.region_id, только по строке, а не по внешнему ключу, так как
    REGTEAM_RAFTING не знает внутренних id сайта."""

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50))  # спортсмен / тренер
    discipline = db.Column(db.String(100))
    rank = db.Column(db.String(100))
    organization = db.Column(db.String(255))
    territory = db.Column(db.String(255))
    national_team = db.Column(db.String(100))
    # Фото спортсмена — из REGTEAM_RAFTING, как и остальные поля (сайт
    # данные не редактирует, только показывает). Пока REGTEAM_RAFTING
    # фото не присылает, поле остаётся пустым — карточка/страница
    # спортсмена в этом случае показывает силуэт-заглушку.
    photo_path = db.Column(db.String(500))
    source_id = db.Column(db.Integer)  # ID в базе REGTEAM_RAFTING
    # Включён ли сейчас в состав сборной (ChangeLog «включён»/«исключён»
    # в REGTEAM_RAFTING) — исключённые не показываются в разделах
    # «Сборная команда» и на страницах клубов, но не удаляются из базы.
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class Referee(db.Model):
    """Судьи — поступают из SPORTS_REFEREE."""

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100))
    disciplines = db.Column(db.String(255))
    territory = db.Column(db.String(255))
    organization = db.Column(db.String(255))
    municipality = db.Column(db.String(150))    # Муниципальное образование
    specialization = db.Column(db.String(300))  # Специализация
    source_id = db.Column(db.Integer)  # ID в базе SPORTS_REFEREE
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class Event(db.Model):
    """Мероприятия (семинары) — поступают из SPORTS_REFEREE."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    event_type = db.Column(db.String(50))  # семинар_судей / семинар_тренеров / семинар_руководителей
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    location = db.Column(db.String(255))
    status = db.Column(db.String(50))  # анонс / идёт / завершён
    # Срок подачи заявок — из блока «Положение о семинаре» в SPORTS_REFEREE
    # (Seminar.polozhenie_applications_deadline), не из start_date/end_date
    # самого семинара: обычно раньше них. Используется в app.py:
    # event_status_label(), чтобы карточка/страница мероприятия показывали
    # «Приём заявок завершён», как только этот срок прошёл — даже если сам
    # семинар (по датам start_date/end_date) ещё не начался.
    applications_deadline = db.Column(db.Date)
    category = db.Column(db.String(100))  # присваиваемая (подтверждаемая) категория
    program_hours = db.Column(db.String(20))  # количество часов программы семинара
    qualification_exam = db.Column(db.String(10))  # квалификационный зачёт: Да/Нет
    leader_full_name = db.Column(db.String(255))  # руководитель семинара
    source_id = db.Column(db.Integer)  # ID в базе SPORTS_REFEREE


class EventDocument(db.Model):
    """Документы мероприятия — тот же приём, что CompetitionDocument.

    doc_type='положение' — файл, загружается вручную через панель
    управления (admin/event_documents.html), как «Положение о
    соревнованиях» у Competition — своего генератора файла на сайте нет,
    сайт данные не редактирует, только показывает то, что загрузили.

    doc_type='протокол' — структурированные данные из SPORTS_REFEREE
    (results_data, JSON-список строк, как CompetitionDocument.results_data
    для протоколов COREZ) — приходят через POST /api/sync/event-protocols
    при нажатии «Отправить на сайт» у семинара."""

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    doc_type = db.Column(db.String(50))  # положение / протокол
    title = db.Column(db.String(255))
    file_path = db.Column(db.String(500))
    results_data = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_published = db.Column(db.Boolean, default=True, nullable=False)

    event = db.relationship('Event', backref=db.backref('documents', cascade='all, delete-orphan'))


class EventLecturer(db.Model):
    """Лекторский состав мероприятия — поступает из SPORTS_REFEREE
    (Seminar.SeminarLecturer) через POST /api/sync/event-lecturers при
    нажатии «Отправить на сайт» у семинара. Список каждый раз заменяется
    целиком (см. routes/api.py: sync_event_lecturers) — как и сам список
    лекторов в SPORTS_REFEREE, где нет отдельных id, устойчивых между
    отправками."""

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    region = db.Column(db.String(255))  # субъект РФ
    qualification = db.Column(db.String(100))  # квалификация спортивного судьи

    event = db.relationship('Event', backref=db.backref('lecturers', cascade='all, delete-orphan'))


class DocumentCategory(db.Model):
    """Категории нормативных документов — определяют пункты бокового меню
    на странице «Рафтинг ЦФО» (список документов), редактируются в панели
    управления. Document.doc_category хранит название категории строкой
    (как News.category у NewsCategory) — привязки по внешнему ключу нет,
    поэтому переименование/удаление категории не трогает уже загруженные
    документы, только отвязывает их от соответствующего пункта меню.

    scope разделяет один и тот же список категорий на независимые боковые
    меню — сейчас используется 'соревнования' (страница «Нормативные
    документы» под Соревнования, competitions.documents), 'мероприятия',
    'оборудование_спортсмены'/'оборудование_организаторы', 'федерация'
    (страница конкретной региональной федерации, regions.documents —
    там же общий список категорий/разделов, а сами документы у каждой
    федерации свои, см. Document.region_id). 'цфо' — то же самое для
    бывшей страницы «Рафтинг ЦФО» (documents.index, страница удалена),
    значение оставлено на случай будущей аналогичной страницы.
    Раздел (DocumentSection) наследует scope родительской категории.

    name уникально только в пределах своего scope (не глобально) —
    разным страницам нужны одинаково называющиеся категории (например,
    «Основополагающие документы» есть и у Соревнований, и у страницы
    федерации). Из-за этого все view, читающие Document.doc_category по
    названию категории (competitions.documents/equipment,
    events.documents, regions.documents), обязаны дополнительно
    ограничивать выборку тем же признаком, что разделяет сами scope у
    Document — то есть либо Document.region_id.is_(None) (для всех
    scope, кроме 'федерация'), либо Document.region_id == region.id
    (для 'федерация') — иначе одинаково названная категория из другого
    scope перепутает документы между страницами."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    scope = db.Column(db.String(30), nullable=False, default='цфо')
    # Порядок вывода среди категорий того же scope — редактируется в
    # панели управления кнопками ▲/▼ (admin/document_taxonomy.html).
    # По умолчанию 0 у всех — тогда сортировка возвращается к алфавитной.
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (db.UniqueConstraint('name', 'scope', name='uq_document_category_name_scope'),)


class DocumentSection(db.Model):
    """Раздел внутри категории документов — привязан к конкретной
    DocumentCategory, редактируется в панели управления вместе с
    категориями (страница «Категории документов»).

    sort_order — порядок вывода внутри категории (по умолчанию 0 у всех,
    тогда сортировка возвращается к алфавитной, как раньше — см. order_by
    ниже) — редактируется в панели управления кнопками ▲/▼
    (admin/document_taxonomy.html)."""

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('document_category.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    category = db.relationship(
        'DocumentCategory',
        backref=db.backref(
            'sections', cascade='all, delete-orphan',
            order_by='DocumentSection.sort_order, DocumentSection.name',
        ),
    )


class DeletedDocumentTaxonomyEntry(db.Model):
    """Категория или раздел из «сеющих» списков вроде
    COMPETITION_DOCUMENT_TAXONOMY (auth.py), удалённые администратором
    через панель управления, — список «не восстанавливать» для функций
    вида ensure_competition_document_taxonomy(), которые при каждом
    старте сервера заново добавляют отсутствующие по названию категории/
    разделы (чтобы новые пункты таксономии подхватывались на уже
    работающих сайтах) и без этого списка не могут отличить «ещё не
    создан» от «удалён вручную».

    section_name пустой (None) — удалена вся категория целиком; иначе
    удалён конкретный раздел внутри неё (сама категория могла остаться)."""

    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(30), nullable=False)
    category_name = db.Column(db.String(100), nullable=False)
    section_name = db.Column(db.String(100))


class EquipmentPageText(db.Model):
    """Вводный текст страницы «Оборудование и снаряжение» (Соревнования)
    — свой у каждой аудитории (audience: 'спортсмены'/'организаторы',
    см. routes/competitions.py: EQUIPMENT_AUDIENCES), редактируется в
    панели управления. Строка создаётся по требованию, как CouncilPage
    — при отсутствии страница показывает «Материалы пока не добавлены»."""

    id = db.Column(db.Integer, primary_key=True)
    audience = db.Column(db.String(20), unique=True, nullable=False)
    text = db.Column(db.Text)


class EquipmentItem(db.Model):
    """Карточка «фото + текст» под конкретным видом оборудования/
    снаряжения (DocumentCategory scope='оборудование_спортсмены'/
    'оборудование_организаторы') — тот же формат, что новости
    (news-row), редактируется в собственном разделе панели управления
    «Оборудование и снаряжение», отдельно от общих новостей сайта."""

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('document_category.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text)
    image_path = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship(
        'DocumentCategory',
        backref=db.backref(
            'equipment_items', cascade='all, delete-orphan',
            order_by='EquipmentItem.sort_order, EquipmentItem.created_at.desc()',
        ),
    )


class Document(db.Model):
    """Нормативные документы."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    doc_category = db.Column(db.String(50))  # см. DocumentCategory — список редактируется в админке
    file_path = db.Column(db.String(500))
    # Вместо загруженного файла в панели управления можно указать внешнюю
    # ссылку — тогда file_path остаётся пустым. Ровно одно из двух должно
    # быть заполнено (проверяется в routes/admin.py, не на уровне БД —
    # там же, где остальные подобные проверки по этой таблице).
    link_url = db.Column(db.String(1000))
    section_id = db.Column(db.Integer, db.ForeignKey('document_section.id'))  # см. DocumentSection, привязан к doc_category
    # Только для документов страницы конкретной федерации (doc_category со
    # scope='федерация') — категории/разделы там общие для всех федераций,
    # а сами документы у каждой федерации свои, поэтому нужна ещё и
    # привязка к конкретной RegionalFederation. Для остальных областей сайта
    # (соревнования/мероприятия/оборудование) документы общие на всех, там
    # region_id остаётся пустым.
    region_id = db.Column(db.Integer, db.ForeignKey('regional_federation.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    section = db.relationship('DocumentSection')
    region = db.relationship('RegionalFederation')


class User(UserMixin, db.Model):
    """Пользователи панели администратора."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='viewer', nullable=False)  # admin / editor / viewer / region_rep
    region = db.Column(db.String(255))  # для role=region_rep — какой регион представляет пользователь
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    # Разделы панели администратора, доступные пользователю (через запятую,
    # см. admin.SECTION_CHOICES) — только для role=editor/viewer, у admin
    # всегда полный доступ независимо от этого поля.
    allowed_sections = db.Column(db.String(255), default='', nullable=False)

    def sections(self):
        return set(filter(None, (self.allowed_sections or '').split(',')))

    def can_access(self, section):
        return self.role == 'admin' or section in self.sections()


class FederationMember(db.Model):
    """Состав органов федерации (исполком, коллегия судей и т.д.).

    local_federation_id — NULL для состава уровня ЦФО (federation.structure(),
    body из 'исполком'/'коллегия_судей'/'тренерский_совет'/'комитет_представителей'),
    заполнено — для состава конкретной местной спортивной федерации
    (routes/local_federations.py: section()), там свои значения body:
    'руководство'/'член_федерации' — под отдельные разделы «Руководство»/
    «Члены Федерации», плюс те же 'коллегия_судей'/'тренерский_совет'/
    'комитет_представителей' — сгруппированы под общим разделом «Коллегии
    и советы» (та же группировка по body, что и на странице ЦФО)."""

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    position = db.Column(db.String(255))
    body = db.Column(db.String(50))  # исполком / коллегия_судей / тренерский_совет / комитет_представителей / руководство / член_федерации
    level = db.Column(db.String(50))  # цфо / регион
    photo_path = db.Column(db.String(500))
    contacts = db.Column(db.String(255))
    local_federation_id = db.Column(db.Integer, db.ForeignKey('local_federation.id'))

    local_federation = db.relationship(
        'LocalFederation', backref=db.backref('members', cascade='all, delete-orphan'),
    )


class RegionalFederation(db.Model):
    """Региональные федерации субъектов ЦФО (страница «Регионы ЦФО» и
    персональная страница каждой федерации по клику на неё)."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    # Наименование субъекта РФ (напр. "Московская область") — короткая
    # форма для группировки клубов по региону на странице «Клубы и
    # команды» (в отличие от полного названия организации в name).
    subject_name = db.Column(db.String(255))
    logo_path = db.Column(db.String(500))  # цветной логотип — круг на карточке/баннере
    # Светлый вариант логотипа для шапки сайта на странице федерации (там
    # тёмный фон) — если не загружен, используется logo_path.
    logo_white_path = db.Column(db.String(500))
    # Общая информация под баннером на странице федерации.
    intro_text = db.Column(db.Text)
    # Разделы бокового меню «О федерации».
    goals_text = db.Column(db.Text)  # Направления деятельности
    councils_intro_text = db.Column(db.Text)  # Коллегии и советы — вводный текст над списком категорий
    contact_phone = db.Column(db.String(100))
    contact_email = db.Column(db.String(150))
    contact_address = db.Column(db.String(500))

    # В шапке сайта на странице конкретной федерации наименование
    # разбивается на 2 строки: часть в кавычках (короткое/торговое
    # название) — заглавными без кавычек в первой строке, часть до
    # кавычек — во второй. Если кавычек в названии нет, всё название
    # выводится одной строкой (name_quoted), а name_before_quote пуст.
    _QUOTE_PAIRS = (('«', '»'), ('"', '"'), ('“', '”'), ('„', '“'))

    def _split_name(self):
        name = self.name or ''
        for open_q, close_q in self._QUOTE_PAIRS:
            start = name.find(open_q)
            if start == -1:
                continue
            end = name.find(close_q, start + len(open_q))
            if end == -1:
                continue
            before = name[:start].strip()
            quoted = name[start + len(open_q):end].strip()
            quoted_full = name[start:end + len(close_q)].strip()
            return before, quoted, quoted_full
        return '', name.strip(), name.strip()

    @property
    def name_before_quote(self):
        return self._split_name()[0]

    @property
    def name_quoted(self):
        return self._split_name()[1]

    @property
    def name_quoted_full(self):
        """Часть названия в кавычках вместе с самими кавычками, без
        изменения регистра — для заголовка на персональной странице
        федерации (fed-page-title), где название переносится на вторую
        строку по границе кавычек, а не режется браузером как попало.
        В отличие от name_quoted (для шапки сайта), кавычки не убираются."""
        return self._split_name()[2]


class CouncilCategory(db.Model):
    """Категория коллегий и советов («Постоянные», «Юрисдикционные» и
    т.п.) — общий список для всех региональных федераций (тот же приём,
    что DocumentCategory: разделы бокового меню общие, а наполнение —
    своё у каждой федерации). Управляется в панели управления
    (admin/council_taxonomy.html) — то же добавление/переименование/
    удаление/перетаскивание, что и у категорий документов."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class Council(db.Model):
    """Коллегия/совет/комитет внутри категории — название общее для всех
    региональных федераций (как раздел документов, DocumentSection), а
    содержимое для конкретной федерации — CouncilPage (вкладка «Общая
    информация») и CouncilMember (вкладка «Состав»), оба со своим
    region_id."""

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('council_category.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    category = db.relationship(
        'CouncilCategory',
        backref=db.backref('councils', cascade='all, delete-orphan', order_by='Council.sort_order, Council.name'),
    )


class CouncilPage(db.Model):
    """Содержимое вкладки «Общая информация» одной коллегии/совета для
    одной конкретной региональной федерации — текст из админки. Строка
    создаётся по требованию (при первом сохранении текста для этой пары
    в админке), поэтому у части (совет, федерация) её может не быть —
    тогда вкладка показывает «Материалы пока не добавлены», как и другие
    ещё не заполненные разделы сайта."""

    id = db.Column(db.Integer, primary_key=True)
    council_id = db.Column(db.Integer, db.ForeignKey('council.id'), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey('regional_federation.id'), nullable=False)
    intro_text = db.Column(db.Text)

    council = db.relationship('Council', backref=db.backref('pages', cascade='all, delete-orphan'))
    region = db.relationship('RegionalFederation')

    __table_args__ = (db.UniqueConstraint('council_id', 'region_id', name='uq_council_page_council_region'),)


class CouncilMember(db.Model):
    """Член коллегии/совета одной конкретной региональной федерации.

    is_chairman — выводится не строкой в списке, а отдельным баннером с
    фото и должностью в заголовке на вкладке «Состав» (обычно один
    человек, но поле не ограничивает количество)."""

    id = db.Column(db.Integer, primary_key=True)
    council_id = db.Column(db.Integer, db.ForeignKey('council.id'), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey('regional_federation.id'), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    position = db.Column(db.String(255))
    photo_path = db.Column(db.String(500))
    is_chairman = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    council = db.relationship('Council', backref=db.backref('members', cascade='all, delete-orphan'))
    region = db.relationship('RegionalFederation')


class LocalFederation(db.Model):
    """Местные спортивные федерации — третий уровень структуры сайта
    (ЦФО → Региональная федерация → Местная федерация), параллельно
    Club. Список показывается в разделе «Местные спортивные федерации»
    на странице региональной федерации-родителя (routes/regions.py),
    персональная страница — по структуре и оформлению повторяющая
    RegionalFederation/Club (routes/local_federations.py).

    Разделы бокового меню персональной страницы: «Руководство»/«Члены
    Федерации»/«Коллегии и советы» — не текстовые поля здесь, а списки
    FederationMember с local_federation_id, указывающим на эту запись
    (см. FederationMember.body); «Календарный план»/«Клубы» — свой
    произвольный текст ниже (список клубов местной федерации не связан
    с моделью Club — вводится вручную)."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey('regional_federation.id'), nullable=False)
    logo_path = db.Column(db.String(500))  # круг на карточке/баннере, как у RegionalFederation.logo_path

    # Общая информация под баннером на странице местной федерации.
    intro_text = db.Column(db.Text)
    calendar_text = db.Column(db.Text)  # Календарный план
    clubs_text = db.Column(db.Text)  # Клубы
    contact_phone = db.Column(db.String(100))
    contact_email = db.Column(db.String(150))
    contact_address = db.Column(db.String(500))

    region = db.relationship('RegionalFederation', backref='local_federations')


class Club(db.Model):
    """Спортивные клубы и организации рафтинга в ЦФО — страница «Клубы и
    команды» (список, сгруппированный по региону) и персональная страница
    клуба, по структуре и оформлению повторяющая RegionalFederation."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey('regional_federation.id'), nullable=False)
    logo_path = db.Column(db.String(500))  # круг на карточке/баннере, как у RegionalFederation.logo_path

    # Общая информация под баннером на странице клуба (пункт «Клуб»).
    intro_text = db.Column(db.Text)
    # Разделы бокового меню страницы клуба.
    leadership_text = db.Column(db.Text)  # Руководство
    coaches_text = db.Column(db.Text)  # Тренеры
    athletes_text = db.Column(db.Text)  # Спортсмены
    schedule_text = db.Column(db.Text)  # Расписание занятий
    achievements_text = db.Column(db.Text)  # Достижения
    contact_phone = db.Column(db.String(100))
    contact_email = db.Column(db.String(150))
    contact_address = db.Column(db.String(500))

    region = db.relationship('RegionalFederation', backref='clubs')


class Banner(db.Model):
    """Рекламные баннеры на страницах сайта — управляются через панель
    администратора. page/position — ключи из BANNER_PAGE_CHOICES /
    BANNER_POSITION_CHOICES в routes/admin.py, определяющие, на какой
    странице и в каком месте страницы показывается баннер."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    image_path = db.Column(db.String(500), nullable=False)
    link_url = db.Column(db.String(500))
    page = db.Column(db.String(50), nullable=False)
    position = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PartnerLogo(db.Model):
    """Логотипы партнёров в полосе перед подвалом (см. base.html) —
    управляются через панель администратора. sort_order определяет
    порядок слева направо."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    image_path = db.Column(db.String(500), nullable=False)
    link_url = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MediaAlbum(db.Model):
    """Фотоальбом — раздел «Медиа» (вкладка «Фото»), добавляется вручную
    через панель администратора. photos_count — просто число для бейджа
    на обложке (сколько фото в альбоме), сами фото не хранятся отдельно."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    cover_path = db.Column(db.String(500), nullable=False)
    photos_count = db.Column(db.Integer, default=1, nullable=False)
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_published = db.Column(db.Boolean, default=True, nullable=False)


class MediaAlbumPhoto(db.Model):
    """Дополнительные фото альбома — сетка на странице альбома (помимо
    обложки MediaAlbum.cover_path, которая идёт на карточку в списке)."""

    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer, db.ForeignKey('media_album.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)

    album = db.relationship('MediaAlbum', backref=db.backref('photos', cascade='all, delete-orphan'))


class MediaVideo(db.Model):
    """Видео — раздел «Медиа» (вкладка «Видео»), добавляется вручную через
    панель администратора. video_url — ссылка на внешнее видео (YouTube/VK
    и т.п.), сам ролик не хранится на сайте."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    thumbnail_path = db.Column(db.String(500), nullable=False)
    video_url = db.Column(db.String(500))
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_published = db.Column(db.Boolean, default=True, nullable=False)


class SyncLog(db.Model):
    """Журнал синхронизации данных, поступающих от COREZ, REGTEAM_RAFTING, SPORTS_REFEREE."""

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(50), nullable=False)  # COREZ / REGTEAM_RAFTING / SPORTS_REFEREE
    sync_type = db.Column(db.String(50))  # competitions / athletes / referees / events
    records_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='success')  # success / error
    message = db.Column(db.String(500))
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)


class FederationRegistrationRequest(db.Model):
    """Заявка на регистрацию региональной федерации — со страницы входа
    («Вход для региональных федераций» в футере), кнопка «Зарегистрироваться».
    Модерируется в панели управления: admin одобряет — тогда создаётся
    User (role=region_rep, username=email, пароль — тот, что ввёл заявитель
    в форме) — либо отклоняет заявку."""

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)  # полное наименование федерации
    short_name = db.Column(db.String(255))  # краткое наименование
    leader_full_name = db.Column(db.String(255), nullable=False)
    leader_position = db.Column(db.String(255))
    phone = db.Column(db.String(100))
    email = db.Column(db.String(150), nullable=False)  # логин для входа
    password_hash = db.Column(db.String(255), nullable=False)

    status = db.Column(db.String(20), default='pending', nullable=False)  # pending / approved / rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime)


class PasswordResetRequest(db.Model):
    """Заявка «Забыли пароль?» со страницы входа — попадает в панель
    управления, admin вручную назначает новый пароль (через редактирование
    пользователя) и отмечает заявку решённой."""

    id = db.Column(db.Integer, primary_key=True)
    username_or_email = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending / resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime)


class SeminarApplicationSubmission(db.Model):
    """Заявка на участие в семинаре — локальная база сайта, источник для
    отображения на вкладке «Участники» страницы мероприятия.

    origin='site' — подана представителем региона через форму на сайте;
    может редактироваться/удаляться автором (submitted_by) или admin.
    origin='referee' — прислана из SPORTS_REFEREE (заявка, внесённая там
    напрямую) кнопкой «Отправить на сайт»; submitted_by_id тогда пуст.

    В SPORTS_REFEREE заявка попадает не автоматически, а только когда
    admin сайта нажмёт «Отправить в считалку» в панели управления (см.
    routes/admin.py, sync_to_referee.py) — до этого send_status='pending'.
    referee_application_id — id этой же заявки в базе SPORTS_REFEREE,
    используется для матчинга при повторной отправке/обновлении в обе
    стороны (и site→referee, и referee→site)."""

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    submitted_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    origin = db.Column(db.String(20), default='site', nullable=False)  # site / referee

    region = db.Column(db.String(150))
    organization_name = db.Column(db.String(300))
    sending_org_name = db.Column(db.String(300))
    sending_org_leader_name = db.Column(db.String(200))
    sending_org_leader_position = db.Column(db.String(150))
    sending_org_leader_phone = db.Column(db.String(100))
    sending_org_leader_email = db.Column(db.String(150))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime)

    send_status = db.Column(db.String(20), default='pending', nullable=False)  # pending / sent / failed
    send_message = db.Column(db.String(500))
    referee_application_id = db.Column(db.Integer)  # id этой же заявки в базе SPORTS_REFEREE

    event = db.relationship('Event', backref=db.backref('application_submissions', cascade='all, delete-orphan'))
    submitted_by = db.relationship('User')


class SeminarApplicationSubmissionParticipant(db.Model):
    """Участник заявки, поданной на сайте — те же поля, что в SPORTS_REFEREE."""

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('seminar_application_submission.id'), nullable=False)

    full_name = db.Column(db.String(200), nullable=False)
    gender = db.Column(db.String(10))
    birth_date = db.Column(db.Date)
    judge_qualification = db.Column(db.String(100))
    assigned_category = db.Column(db.String(100))
    specialization = db.Column(db.String(300))

    submission = db.relationship(
        'SeminarApplicationSubmission', backref=db.backref('participants', cascade='all, delete-orphan'),
    )


class CompetitionApplication(db.Model):
    """Заявка команды на участие в соревновании — локальная база сайта,
    источник для отображения на вкладке «Команды» страницы соревнования.
    По структуре — аналог SeminarApplicationSubmission, но поля названы
    и организованы так, чтобы совпадать с моделью ПредварительнаяЗаявка
    в COREZ (там же и живут спортивные разряды и т.п. — сайт лишь
    зеркалирует ввод).

    origin='site' — подана представителем региона через форму на сайте;
    может редактироваться/удаляться автором (submitted_by) или admin.

    В COREZ заявка попадает не автоматически, а только когда admin сайта
    нажмёт «Отправить в COREZ» в панели управления (см. routes/admin.py,
    sync_to_corez.py) — до этого send_status='pending'.
    corez_application_id — id этой же заявки в базе COREZ
    (ПредварительнаяЗаявка.id), используется для матчинга при повторной
    отправке/обновлении."""

    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey('competition.id'), nullable=False)
    submitted_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    origin = db.Column(db.String(20), default='site', nullable=False)  # site

    region = db.Column(db.String(150))  # субъект_рф
    team_name = db.Column(db.String(300))  # наименование_команды
    # Класс судна и дисциплина — только для отображения на сайте (одно
    # соревнование может проводиться сразу в R4 и R6/по нескольким
    # дисциплинам); в самой ПредварительнаяЗаявка COREZ такого поля нет,
    # при отправке в COREZ не передаются.
    boat_class = db.Column(db.String(20))
    discipline = db.Column(db.String(100))
    # Логотип команды, загруженный вместе с заявкой (в отличие от
    # заявок на семинар, где логотип берётся только из совпадения по
    # названию с RegionalFederation — здесь заявитель может указать
    # логотип команды напрямую). В COREZ не передаётся — ПредварительнаяЗаявка
    # такого поля не хранит.
    logo_path = db.Column(db.String(500))

    org_name = db.Column(db.String(300))  # орг_наименование
    org_leader_name = db.Column(db.String(200))  # орг_фио_руководителя
    org_leader_position = db.Column(db.String(150))  # орг_должность_руководителя
    org_leader_phone = db.Column(db.String(100))  # орг_телефон
    org_leader_email = db.Column(db.String(150))  # орг_email

    coach_full_name = db.Column(db.String(200))  # тренер_фио
    coach_phone = db.Column(db.String(100))  # тренер_телефон
    coach_email = db.Column(db.String(150))  # тренер_email

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime)

    send_status = db.Column(db.String(20), default='pending', nullable=False)  # pending / sent / failed
    send_message = db.Column(db.String(500))
    corez_application_id = db.Column(db.Integer)  # id этой же заявки в базе COREZ

    competition = db.relationship(
        'Competition', backref=db.backref('team_applications', cascade='all, delete-orphan'),
    )
    submitted_by = db.relationship('User')


class CompetitionApplicationAthlete(db.Model):
    """Спортсмен в заявке команды — поля соответствуют модели
    СпортсменЗаявки в COREZ (ФИО раздельно, а не одной строкой, в
    отличие от участника заявки на семинар)."""

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('competition_application.id'), nullable=False)

    last_name = db.Column(db.String(100), nullable=False)  # фамилия
    first_name = db.Column(db.String(100), nullable=False)  # имя
    middle_name = db.Column(db.String(100))  # отчество
    gender = db.Column(db.String(10))  # пол: м/ж
    birth_date = db.Column(db.Date)  # дата_рождения
    qualification = db.Column(db.String(100))  # квалификация (разряд)
    order_number = db.Column(db.String(100))  # номер_приказа
    insurance_number = db.Column(db.String(100))  # номер_страховки
    age_group = db.Column(db.String(100))  # возрастная_группа

    application = db.relationship(
        'CompetitionApplication', backref=db.backref('athletes', cascade='all, delete-orphan'),
    )


class CalendarPlanApplication(db.Model):
    """Заявка на включение соревнования в Единый календарный план (ЕКП) —
    представитель региона предлагает провести новое соревнование, которого
    ещё нет в Competition (в календарный план оно попадает по итогам
    рассмотрения — отдельно, вручную, через COREZ/панель управления, как
    и остальные соревнования). Показывается таблицей на вкладке
    «Соревнования → Календарный план → Формирование календарного плана»
    (routes/competitions.py: calendar()) и полным списком в панели
    управления («Формирование КП», routes/admin.py:
    calendar_applications_list()).

    Состав ГСК и технический делегат — по 4 поля на роль (ФИО,
    квалификация, субъект, город), как в самой заявке; заявитель обычно
    указывает будущего главного судью и себя же в контактах, поэтому
    chief_judge_contact_* не объединены с chief_judge_* — в форме это
    два самостоятельных блока."""

    id = db.Column(db.Integer, primary_key=True)
    submitted_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    competition_name = db.Column(db.String(255))  # Наименование соревнований
    status = db.Column(db.String(200))  # Статус соревнований
    # Возрастная группа и классы судов — как в форме «Добавить соревнование»
    # в COREZ (раздел «Классификация соревнований»): несколько строк
    # возрастная группа + класс(ы) судна, склеенные через " / " (группы) и
    # через пробел (классы), см. _fill_calendar_application_fields().
    age_groups = db.Column(db.String(500))  # Возрастная группа
    boat_classes = db.Column(db.String(20))  # Классы судов (R4 / R6)
    start_date = db.Column(db.Date)  # Дата начала соревнований
    end_date = db.Column(db.Date)  # Дата окончания соревнований
    location_subject = db.Column(db.String(255))  # Место проведения — субъект РФ
    location_details = db.Column(db.String(500))  # Место проведения — район;город;объект спорта
    organizations = db.Column(db.Text)  # Организации, проводящие соревнования
    # Программа соревнований по дням — свободный текст (заезд/оф.тренировка/
    # дисциплины по дням/отъезд с датами), формат не структурируется.
    program_schedule = db.Column(db.Text)

    chief_judge_name = db.Column(db.String(255))  # Главный судья
    chief_judge_qualification = db.Column(db.String(100))
    chief_judge_region = db.Column(db.String(255))
    chief_judge_city = db.Column(db.String(150))

    chief_secretary_name = db.Column(db.String(255))  # Главный секретарь
    chief_secretary_qualification = db.Column(db.String(100))
    chief_secretary_region = db.Column(db.String(255))
    chief_secretary_city = db.Column(db.String(150))

    deputy_judge_name = db.Column(db.String(255))  # Зам. главного судьи по судейству
    deputy_judge_qualification = db.Column(db.String(100))
    deputy_judge_region = db.Column(db.String(255))
    deputy_judge_city = db.Column(db.String(150))

    deputy_organizer_name = db.Column(db.String(255))  # Зам. главного судьи по орг. вопросам
    deputy_organizer_qualification = db.Column(db.String(100))
    deputy_organizer_region = db.Column(db.String(255))
    deputy_organizer_city = db.Column(db.String(150))

    distance_chief_name = db.Column(db.String(255))  # Начальник дистанции
    distance_chief_qualification = db.Column(db.String(100))
    distance_chief_region = db.Column(db.String(255))
    distance_chief_city = db.Column(db.String(150))

    tech_delegate_name = db.Column(db.String(255))  # Технический делегат
    tech_delegate_qualification = db.Column(db.String(100))
    tech_delegate_region = db.Column(db.String(255))
    tech_delegate_city = db.Column(db.String(150))

    # Контакты организаторов
    federation_contact_name = db.Column(db.String(255))  # от Федерации
    federation_contact_phone = db.Column(db.String(50))
    federation_contact_email = db.Column(db.String(150))

    chief_judge_contact_name = db.Column(db.String(255))  # Главный судья (контакт)
    chief_judge_contact_phone = db.Column(db.String(50))
    chief_judge_contact_email = db.Column(db.String(150))

    submitted_by = db.relationship('User')

