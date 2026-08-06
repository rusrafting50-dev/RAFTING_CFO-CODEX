"""API синхронизации данных с COREZ, REGTEAM_RAFTING, SPORTS_REFEREE.

Каждый POST-эндпоинт принимает JSON вида {"items": [...]} и обновляет
соответствующую таблицу по полю source_id (upsert: обновляет существующую
запись или создаёт новую). Запросы защищены заголовком X-API-Key.
"""
import json
import os
from datetime import date
from functools import wraps

from flask import Blueprint, jsonify, request

from models import Athlete, Competition, CompetitionDocument, Event, Referee, SyncLog, db

bp = Blueprint('api', __name__)

SOURCE_BY_SYNC_TYPE = {
    'competitions': 'COREZ',
    'athletes': 'REGTEAM_RAFTING',
    'referees': 'SPORTS_REFEREE',
    'events': 'SPORTS_REFEREE',
    'protocols': 'COREZ',
}

PROTOCOL_DOC_TYPES = ('стартовый_протокол', 'протокол_результатов')
PROTOCOL_TITLES = {
    'стартовый_протокол': 'Стартовый протокол',
    'протокол_результатов': 'Протокол результатов',
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

    created = updated = skipped = 0
    errors = []

    for item in items:
        source_id = item.get('source_id')
        full_name = (item.get('full_name') or '').strip()

        if source_id is None or not full_name:
            skipped += 1
            errors.append(f'source_id={source_id}: отсутствует source_id или full_name')
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

    db.session.commit()
    log_sync('athletes', created + updated,
             message=f'создано: {created}, обновлено: {updated}, пропущено: {skipped}')

    return jsonify({
        'status': 'ok', 'received': len(items),
        'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors,
    })


@bp.route('/sync/referees', methods=['POST'])
@require_api_key
def sync_referees():
    items = get_items_from_request()
    if items is None:
        return jsonify({'error': 'Тело запроса должно быть JSON вида {"items": [...]}.'}), 400

    created = updated = skipped = 0
    errors = []

    for item in items:
        source_id = item.get('source_id')
        full_name = (item.get('full_name') or '').strip()

        if source_id is None or not full_name:
            skipped += 1
            errors.append(f'source_id={source_id}: отсутствует source_id или full_name')
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

    db.session.commit()
    log_sync('referees', created + updated,
             message=f'создано: {created}, обновлено: {updated}, пропущено: {skipped}')

    return jsonify({
        'status': 'ok', 'received': len(items),
        'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors,
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

    db.session.commit()
    log_sync('events', created + updated,
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
    существующий документ соответствующего типа (или создаёт новый).
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
            competition_id=competition.id, doc_type=doc_type,
        ).first()
        if document is None:
            document = CompetitionDocument(competition_id=competition.id, doc_type=doc_type)
            db.session.add(document)
            created += 1
        else:
            updated += 1

        document.title = item.get('title') or PROTOCOL_TITLES[doc_type]
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
