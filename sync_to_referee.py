# sync_to_referee.py — отправка заявки на семинар в проект SPORTS_REFEREE
#
# Заявку на участие в семинаре можно подать прямо на сайте (представителем
# региона) — она сразу сохраняется здесь (SeminarApplicationSubmission,
# см. models.py) и одновременно отправляется в SPORTS_REFEREE через
# POST /api/seminars/<id>/applications (см. его routes/api.py), потому что
# именно SPORTS_REFEREE — источник истины для протоколов семинара.
# Адрес и ключ — SPORTS_REFEREE_URL / SPORTS_REFEREE_API_KEY в .env; ключ
# должен совпадать с API_KEY в .env самого SPORTS_REFEREE.
import os

import requests

SPORTS_REFEREE_URL = os.environ.get('SPORTS_REFEREE_URL', 'http://127.0.0.1:5002').rstrip('/')
SPORTS_REFEREE_API_KEY = os.environ.get('SPORTS_REFEREE_API_KEY', '')


def _собрать_данные(submission):
    return {
        'region': submission.region,
        'organization_name': submission.organization_name,
        'sending_org_name': submission.sending_org_name,
        'sending_org_leader_name': submission.sending_org_leader_name,
        'sending_org_leader_position': submission.sending_org_leader_position,
        'sending_org_leader_phone': submission.sending_org_leader_phone,
        'sending_org_leader_email': submission.sending_org_leader_email,
        'submitted_at': submission.created_at.isoformat(),
        'participants': [
            {
                'full_name': p.full_name,
                'gender': p.gender,
                'birth_date': p.birth_date.isoformat() if p.birth_date else None,
                'judge_qualification': p.judge_qualification,
                'assigned_category': p.assigned_category,
                'specialization': p.specialization,
            }
            for p in submission.participants
        ],
    }


def отправить_заявку(submission, seminar_source_id):
    """Отправляет заявку в SPORTS_REFEREE. Возвращает (успех, сообщение,
    referee_application_id)."""
    if not SPORTS_REFEREE_API_KEY:
        return False, 'SPORTS_REFEREE_API_KEY не задан в .env — см. .env.example', None

    try:
        ответ = requests.post(
            f'{SPORTS_REFEREE_URL}/api/seminars/{seminar_source_id}/applications',
            json=_собрать_данные(submission),
            headers={'X-API-Key': SPORTS_REFEREE_API_KEY},
            timeout=10,
        )
    except requests.RequestException as exc:
        return False, f'Не удалось соединиться с SPORTS_REFEREE ({SPORTS_REFEREE_URL}): {exc}', None

    if ответ.status_code != 200:
        return False, f'SPORTS_REFEREE ответил ошибкой {ответ.status_code}: {ответ.text[:200]}', None

    данные = ответ.json()
    return True, 'Заявка отправлена в SPORTS_REFEREE.', данные.get('application_id')


def запросить_заявки(seminar_source_id):
    """Запрашивает у SPORTS_REFEREE список уже поданных заявок по семинару
    (для отображения на вкладке «Участники»). Возвращает (список, ошибка) —
    при недоступности SPORTS_REFEREE список пуст, а ошибка — текст для
    показа вместо списка."""
    if not SPORTS_REFEREE_API_KEY:
        return [], 'SPORTS_REFEREE_API_KEY не задан в .env — см. .env.example'

    try:
        ответ = requests.get(
            f'{SPORTS_REFEREE_URL}/api/seminars/{seminar_source_id}/applications',
            headers={'X-API-Key': SPORTS_REFEREE_API_KEY},
            timeout=5,
        )
    except requests.RequestException:
        return [], 'Не удалось соединиться с SPORTS_REFEREE — список заявок временно недоступен.'

    if ответ.status_code != 200:
        return [], 'SPORTS_REFEREE ответил ошибкой — список заявок временно недоступен.'

    данные = ответ.json()
    return данные.get('items', []), None
