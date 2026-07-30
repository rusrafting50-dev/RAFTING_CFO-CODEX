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
    category = db.Column(db.String(50))  # соревнование / мероприятие / федерация
    level = db.Column(db.String(50))  # цфо / регион / отделение / клуб
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))

    author = db.relationship('User', backref='news_items')


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


class FederationMember(db.Model):
    """Состав органов федерации (исполком, коллегия судей и т.д.)."""

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    position = db.Column(db.String(255))
    body = db.Column(db.String(50))  # исполком / коллегия_судей / тренерский_совет / комитет_представителей
    level = db.Column(db.String(50))  # цфо / регион
    photo_path = db.Column(db.String(500))
    contacts = db.Column(db.String(255))


class SyncLog(db.Model):
    """Журнал синхронизации данных, поступающих от COREZ, REGTEAM_RAFTING, SPORTS_REFEREE."""

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(50), nullable=False)  # COREZ / REGTEAM_RAFTING / SPORTS_REFEREE
    sync_type = db.Column(db.String(50))  # competitions / athletes / referees / events
    records_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='success')  # success / error
    message = db.Column(db.String(500))
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)
