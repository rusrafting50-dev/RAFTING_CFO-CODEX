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
    source_id = db.Column(db.Integer)  # ID в базе SPORTS_REFEREE


class Document(db.Model):
    """Нормативные документы."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    doc_category = db.Column(db.String(50))  # федеральный / региональный / wrf / фрр / федерация
    file_path = db.Column(db.String(500))
    level = db.Column(db.String(50))  # цфо / регион
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class User(UserMixin, db.Model):
    """Пользователи панели администратора."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='viewer', nullable=False)  # admin / editor / viewer
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


class SyncLog(db.Model):
    """Журнал синхронизации данных, поступающих от COREZ, REGTEAM_RAFTING, SPORTS_REFEREE."""

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(50), nullable=False)  # COREZ / REGTEAM_RAFTING / SPORTS_REFEREE
    sync_type = db.Column(db.String(50))  # competitions / athletes / referees / events
    records_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='success')  # success / error
    message = db.Column(db.String(500))
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)
