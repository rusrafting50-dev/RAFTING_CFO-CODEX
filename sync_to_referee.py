# sync_to_referee.py — отправка заявки на семинар в проект SPORTS_REFEREE
#
# Заявки подаются на сайте через форму (SeminarApplicationSubmission,
# см. models.py) и хранятся локально — сайт сам является источником для
# отображения на вкладке «Участники». В SPORTS_REFEREE (источник истины
# для протоколов семинара) заявка попадает не автоматически, а только
# когда admin сайта нажмёт «Отправить в считалку» в панели управления
# (см. routes/admin.py) — через POST при первой отправке или PUT при
# повторной (обновление уже отправленной заявки).
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
    """Отправляет НОВУЮ заявку в SPORTS_REFEREE (первая отправка). Возвращает
    (успех, сообщение, referee_application_id)."""
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


def обновить_заявку(submission, seminar_source_id, referee_application_id):
    """Обновляет уже отправленную ранее заявку в SPORTS_REFEREE (повторное
    нажатие «Отправить в считалку» после редактирования). Возвращает
    (успех, сообщение)."""
    ключ = _ключ()
    if not ключ:
        return False, 'SPORTS_REFEREE_API_KEY не задан в .env — см. .env.example'

    адрес = _адрес()
    try:
        ответ = requests.put(
            f'{адрес}/api/seminars/{seminar_source_id}/applications/{referee_application_id}',
            json=_собрать_данные(submission),
            headers={'X-API-Key': ключ},
            timeout=10,
        )
    except requests.RequestException as exc:
        return False, f'Не удалось соединиться с SPORTS_REFEREE ({адрес}): {exc}'

    if ответ.status_code == 404:
        return False, 'Заявка не найдена на SPORTS_REFEREE (возможно, была удалена там) — отправьте как новую.'
    if ответ.status_code == 401:
        return False, 'SPORTS_REFEREE отклонил запрос: неверный SPORTS_REFEREE_API_KEY.'
    if ответ.status_code != 200:
        return False, f'SPORTS_REFEREE ответил ошибкой {ответ.status_code}: {ответ.text[:200]}'

    return True, 'Заявка обновлена в SPORTS_REFEREE.'
