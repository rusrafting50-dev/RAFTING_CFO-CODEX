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

    author = db.relationship('User', backref='news_items')


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
    status = db.Column(db.String(50))  # анонс / идёт / завершены
    source_id = db.Column(db.Integer)  # ID в базе COREZ
    # Из карточки соревнования COREZ — для отображения в том же виде на сайте.
    age_group = db.Column(db.String(255))  # возрастная группа (напр. "Мужчины, женщины")
    boat_class = db.Column(db.String(20))  # класс судна: R4 / R6 / R4/R6
    head_judge = db.Column(db.String(255))  # гл. судья соревнований
    registration_number = db.Column(db.String(100))  # № ЕКП
    logo_path = db.Column(db.String(500))  # логотип соревнования (относительно static/)

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


class Athlete(db.Model):
    """Спортсмены и тренеры сборной — поступают из REGTEAM_RAFTING."""

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50))  # спортсмен / тренер
    discipline = db.Column(db.String(100))
    rank = db.Column(db.String(100))
    organization = db.Column(db.String(255))
    territory = db.Column(db.String(255))
    national_team = db.Column(db.String(100))
    source_id = db.Column(db.Integer)  # ID в базе REGTEAM_RAFTING


class Referee(db.Model):
    """Судьи — поступают из SPORTS_REFEREE."""

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100))
    disciplines = db.Column(db.String(255))
    territory = db.Column(db.String(255))
    organization = db.Column(db.String(255))
    source_id = db.Column(db.Integer)  # ID в базе SPORTS_REFEREE


class Event(db.Model):
    """Мероприятия (семинары) — поступают из SPORTS_REFEREE."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    event_type = db.Column(db.String(50))  # семинар_судей / семинар_тренеров / семинар_руководителей
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    location = db.Column(db.String(255))
    status = db.Column(db.String(50))  # анонс / идёт / завершён
    category = db.Column(db.String(100))  # присваиваемая (подтверждаемая) категория
    program_hours = db.Column(db.String(20))  # количество часов программы семинара
    qualification_exam = db.Column(db.String(10))  # квалификационный зачёт: Да/Нет
    leader_full_name = db.Column(db.String(255))  # руководитель семинара
    source_id = db.Column(db.Integer)  # ID в базе SPORTS_REFEREE


class DocumentCategory(db.Model):
    """Категории нормативных документов — определяют пункты бокового меню
    на странице «Рафтинг ЦФО» (список документов), редактируются в панели
    управления. Document.doc_category хранит название категории строкой
    (как News.category у NewsCategory) — привязки по внешнему ключу нет,
    поэтому переименование/удаление категории не трогает уже загруженные
    документы, только отвязывает их от соответствующего пункта меню."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)


class Document(db.Model):
    """Нормативные документы."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    doc_category = db.Column(db.String(50))  # см. DocumentCategory — список редактируется в админке
    file_path = db.Column(db.String(500))
    level = db.Column(db.String(50))  # цфо / регион
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


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
    """Состав органов федерации (исполком, коллегия судей и т.д.)."""

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    position = db.Column(db.String(255))
    body = db.Column(db.String(50))  # исполком / коллегия_судей / тренерский_совет / комитет_представителей
    level = db.Column(db.String(50))  # цфо / регион
    photo_path = db.Column(db.String(500))
    contacts = db.Column(db.String(255))


class RegionalFederation(db.Model):
    """Региональные федерации субъектов ЦФО (страница «Регионы ЦФО»)."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    logo_path = db.Column(db.String(500))


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
