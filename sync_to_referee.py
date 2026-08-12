# sync_to_referee.py — отправка заявки на семинар в проект SPORTS_REFEREE
#
# Заявку на участие в семинаре можно подать прямо на сайте (представителем
# региона) — она сразу сохраняется здесь (SeminarApplicationSubmission,
# см. models.py) и одновременно отправляется в SPORTS_REFEREE через
# POST /api/seminars/<id>/applications (см. его routes/api.py), потому что
# именно SPORTS_REFEREE — источник истины для протоколов семинара.
# Адрес и ключ — SPORTS_REFEREE_URL / SPORTS_REFEREE_API_KEY в .env; ключ
# должен совпадать с API_KEY в .env самого SPORTS_REFEREE.
#
# Значения читаются из os.environ при каждом вызове (не на уровне модуля),
# чтобы правка .env не требовала полного перезапуска процесса —
# Flask-автоперезагрузчик следит только за .py-файлами.
import os

import requests


def _адрес():
    return os.environ.get('SPORTS_REFEREE_URL', 'http://127.0.0.1:5002').rstrip('/')


def _ключ():
    return os.environ.get('SPORTS_REFEREE_API_KEY', '')


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
    ключ = _ключ()
    if not ключ:
        return False, 'SPORTS_REFEREE_API_KEY не задан в .env — см. .env.example', None

    адрес = _адрес()
    try:
        ответ = requests.post(
            f'{адрес}/api/seminars/{seminar_source_id}/applications',
            json=_собрать_данные(submission),
            headers={'X-API-Key': ключ},
            timeout=10,
        )
    except requests.RequestException as exc:
        return False, f'Не удалось соединиться с SPORTS_REFEREE ({адрес}): {exc}', None

    if ответ.status_code == 404:
        return False, f'Семинар не найден на SPORTS_REFEREE (source_id={seminar_source_id}).', None
    if ответ.status_code == 401:
        return False, 'SPORTS_REFEREE отклонил запрос: неверный SPORTS_REFEREE_API_KEY.', None
    if ответ.status_code != 200:
        return False, f'SPORTS_REFEREE ответил ошибкой {ответ.status_code}: {ответ.text[:200]}', None

    данные = ответ.json()
    return True, 'Заявка отправлена в SPORTS_REFEREE.', данные.get('application_id')


def запросить_заявки(seminar_source_id):
    """Запрашивает у SPORTS_REFEREE список уже поданных заявок по семинару
    (для отображения на вкладке «Участники»). Возвращает (список, ошибка) —
    при недоступности SPORTS_REFEREE список пуст, а ошибка — текст для
    показа вместо списка."""
    ключ = _ключ()
    if not ключ:
        return [], 'SPORTS_REFEREE_API_KEY не задан в .env — см. .env.example'

    адрес = _адрес()
    try:
        ответ = requests.get(
            f'{адрес}/api/seminars/{seminar_source_id}/applications',
            headers={'X-API-Key': ключ},
            timeout=5,
        )
    except requests.RequestException as exc:
        return [], f'Не удалось соединиться с SPORTS_REFEREE ({адрес}): {exc}'

    if ответ.status_code == 404:
        return [], f'Семинар не найден на SPORTS_REFEREE (source_id={seminar_source_id}) — заявки не отображаются.'
    if ответ.status_code == 401:
        return [], 'SPORTS_REFEREE отклонил запрос: неверный SPORTS_REFEREE_API_KEY.'
    if ответ.status_code != 200:
        return [], f'SPORTS_REFEREE ответил ошибкой {ответ.status_code} — список заявок временно недоступен.'

    данные = ответ.json()
    return данные.get('items', []), None
