"""API синхронизации данных с COREZ, REGTEAM_RAFTING, SPORTS_REFEREE.

Каждый POST-эндпоинт принимает JSON вида {"items": [...]} и обновляет
соответствующую таблицу по полю source_id (upsert: обновляет существующую
запись или создаёт новую). Запросы защищены заголовком X-API-Key.
"""
import base64
import binascii
import json
import os
from datetime import date, datetime
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from models import (
    Athlete, Competition, CompetitionDocument, Event, Referee,
    SeminarApplicationSubmission, SeminarApplicationSubmissionParticipant, SyncLog, db,
)
from utils import safe_upload_filename

bp = Blueprint('api', __name__)

SOURCE_BY_SYNC_TYPE = {
    'competitions': 'COREZ',
    'athletes': 'REGTEAM_RAFTING',
    'referees': 'SPORTS_REFEREE',
    'events': 'SPORTS_REFEREE',
    'seminar_applications': 'SPORTS_REFEREE',
    'protocols': 'COREZ',
}

PROTOCOL_DOC_TYPES = (
    'стартовый_протокол', 'протокол_результатов',
    'результаты_спринт', 'результаты_пс', 'результаты_слалом',
    'результаты_дг', 'результаты_мб',
)
PROTOCOL_TITLES = {
    'стартовый_протокол': 'Стартовый протокол',
    'протокол_результатов': 'Протокол результатов',
    'результаты_спринт': 'Результаты — спринт',
    'результаты_пс': 'Результаты — параллельный спринт',
    'результаты_слалом': 'Результаты — слалом',
    'результаты_дг': 'Результаты — длинная гонка',
    'результаты_мб': 'Результаты — многоборье',
}


def require_api_key(view):
    """Проверяет заголовок X-API-Key на соответствие значению из .env."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected_key = os.environ.get('API_KEY')
        provided_key = request.headers.get('X-API-Key')

        if not expected_key:
            return jsonify({'error': 'API-ключ не настроен на сервере.'}), 500
        if not provided_key or provided_key != expected_key:
            return jsonify({'error': 'Неверный или отсутствующий X-API-Key.'}), 401

        return view(*args, **kwargs)
    return wrapped


def parse_date(value):
    """Парсит дату вида YYYY-MM-DD. Пустое значение — None. Неверный формат — ValueError."""
    if not value:
        return None
    return date.fromisoformat(value)


def log_sync(sync_type, records_count, status='success', message=''):
    log = SyncLog(
        source=SOURCE_BY_SYNC_TYPE[sync_type],
        sync_type=sync_type,
        records_count=records_count,
        status=status,
        message=message[:500],
    )
    db.session.add(log)
    db.session.commit()


ALLOWED_LOGO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'}


def save_logo_from_base64(filename, b64_data):
    """Декодирует логотип, присланный в base64 (файлы по API не передать
    напрямую — COREZ шлёт JSON), и сохраняет в UPLOAD_FOLDER. Возвращает
    путь относительно static/ или None, если формат/данные не подошли."""
    if not filename or '.' not in filename:
        return None
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        return None
    try:
        raw = base64.b64decode(b64_data, validate=True)
    except (binascii.Error, ValueError):
        return None

    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    unique_name = f"{datetime.utcnow():%Y%m%d%H%M%S}_{safe_upload_filename(filename)}"
    with open(os.path.join(upload_dir, unique_name), 'wb') as f:
        f.write(raw)
    return f"uploads/{unique_name}"


def get_items_from_request():
    """Возвращает список записей из тела запроса или None, если формат неверный."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None
    items = payload.get('items')
    return items if isinstance(items, list) else None


@bp.route('/sync/competitions', methods=['POST'])
@require_api_key
def sync_competitions():
    items = get_items_from_request()
    if items is None:
        return jsonify({'error': 'Тело запроса должно быть JSON вида {"items": [...]}.'}), 400

    created = updated = skipped = 0
    errors = []

    for item in items:
        source_id = item.get('source_id')
        name = (item.get('name') or '').strip()

        if source_id is None or not name:
            skipped += 1
            errors.append(f'source_id={source_id}: отсутствует source_id или name')
            continue

        try:
            start_date = parse_date(item.get('start_date'))
            end_date = parse_date(item.get('end_date'))
        except ValueError:
            skipped += 1
            errors.append(f'source_id={source_id}: неверный формат даты (ожидается YYYY-MM-DD)')
            continue

        competition = Competition.query.filter_by(source_id=source_id).first()
        if competition is None:
            competition = Competition(source_id=source_id)
            db.session.add(competition)
            created += 1
        else:
            updated += 1

        competition.name = name
        competition.comp_type = item.get('comp_type')
        competition.level = item.get('level')
        competition.start_date = start_date
        competition.end_date = end_date
        competition.location = item.get('location')
        competition.status = item.get('status')
        competition.age_group = item.get('age_group')
        competition.boat_class = item.get('boat_class')
        competition.head_judge = item.get('head_judge')
        competition.registration_number = item.get('registration_number')

        logo_filename = item.get('logo_filename')
        logo_base64 = item.get('logo_base64')
        if logo_filename and logo_base64:
            saved_path = save_logo_from_base64(logo_filename, logo_base64)
            if saved_path:
                competition.logo_path = saved_path
            else:
                errors.append(f'source_id={source_id}: логотип не сохранён (неверный формат/данные)')
        else:
            # COREZ шлёт logo_filename/logo_base64 в каждой отправке (null,
            # если у соревнования логотип убрали) — раз их нет и сейчас,
            # это значит логотип убрали, а не что поле просто не пришло.
            competition.logo_path = None

    db.session.commit()
    log_sync('competitions', created + updated,
             message=f'создано: {created}, обновлено: {updated}, пропущено: {skipped}')

    return jsonify({
        'status': 'ok', 'received': len(items),
        'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors,
    })


@bp.route('/sync/athletes', methods=['POST'])
@require_api_key
def sync_athletes():
    items = get_items_from_request()
    if items is None:
        return jsonify({'error': 'Тело запроса должно быть JSON вида {"items": [...]}.'}), 400

    created = updated = deleted = skipped = 0
    errors = []

    for item in items:
        source_id = item.get('source_id')

        if source_id is None:
            skipped += 1
            errors.append('отсутствует source_id')
            continue

        if item.get('deleted'):
            # Спортсмен/тренер удалён совсем (не просто исключён из
            # состава — для этого есть is_active) — например, запись
            # была создана по ошибке. Молча пропускаем, если такого
            # source_id и так уже нет.
            removed = Athlete.query.filter_by(source_id=source_id).delete()
            if removed:
                deleted += 1
            continue

        full_name = (item.get('full_name') or '').strip()
        if not full_name:
            skipped += 1
            errors.append(f'source_id={source_id}: отсутствует full_name')
            continue

        athlete = Athlete.query.filter_by(source_id=source_id).first()
        if athlete is None:
            athlete = Athlete(source_id=source_id)
            db.session.add(athlete)
            created += 1
        else:
            updated += 1

        athlete.full_name = full_name
        athlete.role = item.get('role')
        athlete.discipline = item.get('discipline')
        athlete.rank = item.get('rank')
        athlete.organization = item.get('organization')
        athlete.territory = item.get('territory')
        athlete.national_team = item.get('national_team')
        athlete.is_active = bool(item.get('is_active', True))

    db.session.commit()
    log_sync('athletes', created + updated + deleted,
             message=f'создано: {created}, обновлено: {updated}, удалено: {deleted}, пропущено: {skipped}')

    return jsonify({
        'status': 'ok', 'received': len(items),
        'created': created, 'updated': updated, 'deleted': deleted, 'skipped': skipped, 'errors': errors,
    })


@bp.route('/sync/referees', methods=['POST'])
@require_api_key
def sync_referees():
    items = get_items_from_request()
    if items is None:
        return jsonify({'error': 'Тело запроса должно быть JSON вида {"items": [...]}.'}), 400

    created = updated = deleted = skipped = 0
    errors = []

    for item in items:
        source_id = item.get('source_id')

        if source_id is None:
            skipped += 1
            errors.append('отсутствует source_id')
            continue

        if item.get('deleted'):
            # Судья удалён совсем (не просто исключён из активного
            # списка — для этого есть is_active). Молча пропускаем, если
            # такого source_id и так уже нет.
            removed = Referee.query.filter_by(source_id=source_id).delete()
            if removed:
                deleted += 1
            continue

        full_name = (item.get('full_name') or '').strip()
        if not full_name:
            skipped += 1
            errors.append(f'source_id={source_id}: отсутствует full_name')
            continue

        referee = Referee.query.filter_by(source_id=source_id).first()
        if referee is None:
            referee = Referee(source_id=source_id)
            db.session.add(referee)
            created += 1
        else:
            updated += 1

        referee.full_name = full_name
        referee.category = item.get('category')
        referee.disciplines = item.get('disciplines')
        referee.territory = item.get('territory')
        referee.organization = item.get('organization')
        referee.municipality = item.get('municipality')
        referee.specialization = item.get('specialization')
        referee.is_active = bool(item.get('is_active', True))

    db.session.commit()
    log_sync('referees', created + updated + deleted,
             message=f'создано: {created}, обновлено: {updated}, удалено: {deleted}, пропущено: {skipped}')

    return jsonify({
        'status': 'ok', 'received': len(items),
        'created': created, 'updated': updated, 'deleted': deleted, 'skipped': skipped, 'errors': errors,
    })


@bp.route('/sync/events', methods=['POST'])
@require_api_key
def sync_events():
    items = get_items_from_request()
    if items is None:
        return jsonify({'error': 'Тело запроса должно быть JSON вида {"items": [...]}.'}), 400

    created = updated = skipped = 0
    errors = []

    for item in items:
        source_id = item.get('source_id')
        name = (item.get('name') or '').strip()

        if source_id is None or not name:
            skipped += 1
            errors.append(f'source_id={source_id}: отсутствует source_id или name')
            continue

        try:
            start_date = parse_date(item.get('start_date'))
            end_date = parse_date(item.get('end_date'))
        except ValueError:
            skipped += 1
            errors.append(f'source_id={source_id}: неверный формат даты (ожидается YYYY-MM-DD)')
            continue

        event = Event.query.filter_by(source_id=source_id).first()
        if event is None:
            event = Event(source_id=source_id)
            db.session.add(event)
            created += 1
        else:
            updated += 1

        event.name = name
        event.event_type = item.get('event_type')
        event.start_date = start_date
        event.end_date = end_date
        event.location = item.get('location')
        event.status = item.get('status')
        event.category = item.get('category')
        event.program_hours = item.get('program_hours')
        event.qualification_exam = item.get('qualification_exam')
        event.leader_full_name = item.get('leader_full_name')

    db.session.commit()
    log_sync('events', created + updated,
             message=f'создано: {created}, обновлено: {updated}, пропущено: {skipped}')

    return jsonify({
        'status': 'ok', 'received': len(items),
        'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors,
    })


@bp.route('/sync/seminar-applications', methods=['POST'])
@require_api_key
def sync_seminar_applications():
    """Принимает заявку, отправленную из SPORTS_REFEREE кнопкой «Отправить
    на сайт» (заявка, внесённая непосредственно там, не с сайта). Матчинг —
    по referee_application_id (id этой же заявки в базе SPORTS_REFEREE):
    повторная отправка той же заявки обновляет уже существующую запись,
    а не создаёт дубликат."""
    items = get_items_from_request()
    if items is None:
        return jsonify({'error': 'Тело запроса должно быть JSON вида {"items": [...]}.'}), 400

    created = updated = skipped = 0
    errors = []

    for item in items:
        seminar_source_id = item.get('seminar_source_id')
        referee_application_id = item.get('referee_application_id')
        participants_raw = item.get('participants')

        if seminar_source_id is None or referee_application_id is None or not isinstance(participants_raw, list):
            skipped += 1
            errors.append(
                f'referee_application_id={referee_application_id}: '
                'нужны seminar_source_id, referee_application_id и participants (список)'
            )
            continue

        event = Event.query.filter_by(source_id=seminar_source_id).first()
        if event is None:
            skipped += 1
            errors.append(f'seminar_source_id={seminar_source_id}: мероприятие не найдено на сайте')
            continue

        submission = SeminarApplicationSubmission.query.filter_by(
            referee_application_id=referee_application_id,
        ).first()
        if submission is None:
            submission = SeminarApplicationSubmission(
                event_id=event.id, origin='referee', referee_application_id=referee_application_id,
            )
            submitted_at = item.get('submitted_at')
            try:
                submission.created_at = datetime.fromisoformat(submitted_at) if submitted_at else datetime.utcnow()
            except ValueError:
                submission.created_at = datetime.utcnow()
            db.session.add(submission)
            created += 1
        else:
            submission.updated_at = datetime.utcnow()
            updated += 1

        submission.region = (item.get('region') or '').strip() or None
        submission.organization_name = (item.get('organization_name') or '').strip() or None
        submission.sending_org_name = (item.get('sending_org_name') or '').strip() or None
        submission.sending_org_leader_name = (item.get('sending_org_leader_name') or '').strip() or None
        submission.sending_org_leader_position = (item.get('sending_org_leader_position') or '').strip() or None
        submission.sending_org_leader_phone = (item.get('sending_org_leader_phone') or '').strip() or None
        submission.sending_org_leader_email = (item.get('sending_org_leader_email') or '').strip() or None
        db.session.flush()

        SeminarApplicationSubmissionParticipant.query.filter_by(submission_id=submission.id).delete()
        for p in participants_raw:
            full_name = (p.get('full_name') or '').strip()
            if not full_name:
                continue
            try:
                birth_date = parse_date(p.get('birth_date'))
            except ValueError:
                birth_date = None
            db.session.add(SeminarApplicationSubmissionParticipant(
                submission_id=submission.id,
                full_name=full_name,
                gender=(p.get('gender') or '').strip() or None,
                birth_date=birth_date,
                judge_qualification=(p.get('judge_qualification') or '').strip() or None,
                assigned_category=(p.get('assigned_category') or '').strip() or None,
                specialization=(p.get('specialization') or '').strip() or None,
            ))

    db.session.commit()
    log_sync('seminar_applications', created + updated,
             message=f'создано: {created}, обновлено: {updated}, пропущено: {skipped}')

    return jsonify({
        'status': 'ok', 'received': len(items),
        'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors,
    })


@bp.route('/sync/protocols', methods=['POST'])
@require_api_key
def sync_protocols():
    """Принимает от COREZ структурированные стартовые протоколы / протоколы результатов.

    Каждый элемент привязывается к соревнованию по его source_id и заменяет
    существующий документ с тем же doc_type+title (или создаёт новый) — по
    title, а не только по doc_type, потому что один и тот же doc_type
    (например, протокол_результатов) может состоять из нескольких отдельных
    таблиц с разными заголовками (спринт — R4/R6 × мужчины/женщины и т.д.),
    и они не должны затирать друг друга.
    """
    items = get_items_from_request()
    if items is None:
        return jsonify({'error': 'Тело запроса должно быть JSON вида {"items": [...]}.'}), 400

    created = updated = skipped = 0
    errors = []

    for item in items:
        competition_source_id = item.get('competition_source_id')
        doc_type = item.get('doc_type')
        rows = item.get('rows')
        title = item.get('title') or PROTOCOL_TITLES.get(doc_type)

        if (
            competition_source_id is None
            or doc_type not in PROTOCOL_DOC_TYPES
            or not isinstance(rows, list)
        ):
            skipped += 1
            errors.append(
                f'competition_source_id={competition_source_id}: '
                'нужны competition_source_id, doc_type (стартовый_протокол/протокол_результатов) и rows (список)'
            )
            continue

        competition = Competition.query.filter_by(source_id=competition_source_id).first()
        if competition is None:
            skipped += 1
            errors.append(f'competition_source_id={competition_source_id}: соревнование не найдено')
            continue

        document = CompetitionDocument.query.filter_by(
            competition_id=competition.id, doc_type=doc_type, title=title,
        ).first()
        if document is None:
            document = CompetitionDocument(competition_id=competition.id, doc_type=doc_type)
            db.session.add(document)
            created += 1
        else:
            updated += 1

        document.title = title
        document.results_data = json.dumps(rows, ensure_ascii=False)

    db.session.commit()
    log_sync('protocols', created + updated,
             message=f'создано: {created}, обновлено: {updated}, пропущено: {skipped}')

    return jsonify({
        'status': 'ok', 'received': len(items),
        'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors,
    })


@bp.route('/status')
def status():
    """Публичный статус синхронизации — последний успешный запрос по каждому источнику."""
    result = {}
    for source in ('COREZ', 'REGTEAM_RAFTING', 'SPORTS_REFEREE'):
        log = SyncLog.query.filter_by(source=source).order_by(SyncLog.synced_at.desc()).first()
        result[source] = {
            'last_synced_at': log.synced_at.isoformat() if log else None,
            'sync_type': log.sync_type if log else None,
            'records_count': log.records_count if log else None,
            'status': log.status if log else None,
        }
    return jsonify(result)
