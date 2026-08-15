# sync_to_corez.py — отправка заявки команды на соревнование в проект COREZ
#
# Заявки подаются на сайте через форму (CompetitionApplication, см.
# models.py) и хранятся локально — сайт сам является источником для
# отображения на вкладке «Команды» страницы соревнования. В COREZ (модель
# ПредварительнаяЗаявка) заявка попадает не автоматически, а только когда
# admin сайта нажмёт «Отправить в COREZ» в панели управления (см.
# routes/admin.py) — через POST при первой отправке или PUT при повторной
# (обновление уже отправленной заявки).
# Адрес и ключ — COREZ_URL / COREZ_API_KEY в .env; ключ должен совпадать
# с API_KEY в .env самого COREZ.
#
# Значения читаются из os.environ при каждом вызове (не на уровне модуля),
# чтобы правка .env не требовала полного перезапуска процесса —
# Flask-автоперезагрузчик следит только за .py-файлами.
import os

import requests


def _адрес():
    return os.environ.get('COREZ_URL', 'http://127.0.0.1:5000').rstrip('/')


def _ключ():
    return os.environ.get('COREZ_API_KEY', '')


def _собрать_данные(application):
    return {
        'субъект_рф': application.region,
        'наименование_команды': application.team_name,
        'орг_наименование': application.org_name,
        'орг_фио_руководителя': application.org_leader_name,
        'орг_должность_руководителя': application.org_leader_position,
        'орг_телефон': application.org_leader_phone,
        'орг_email': application.org_leader_email,
        'тренер_фио': application.coach_full_name,
        'тренер_телефон': application.coach_phone,
        'тренер_email': application.coach_email,
        'подано': application.created_at.isoformat(),
        'спортсмены': [
            {
                'фамилия': a.last_name,
                'имя': a.first_name,
                'отчество': a.middle_name,
                'пол': a.gender,
                'дата_рождения': a.birth_date.isoformat() if a.birth_date else None,
                'квалификация': a.qualification,
                'номер_приказа': a.order_number,
                'номер_страховки': a.insurance_number,
                'возрастная_группа': a.age_group,
            }
            for a in application.athletes
        ],
    }


def отправить_заявку_команды(application, competition_source_id):
    """Отправляет НОВУЮ заявку команды в COREZ (первая отправка). Возвращает
    (успех, сообщение, corez_application_id)."""
    ключ = _ключ()
    if not ключ:
        return False, 'COREZ_API_KEY не задан в .env — см. .env.example', None

    адрес = _адрес()
    try:
        ответ = requests.post(
            f'{адрес}/api/competitions/{competition_source_id}/applications',
            json=_собрать_данные(application),
            headers={'X-API-Key': ключ},
            timeout=10,
        )
    except requests.RequestException as exc:
        return False, f'Не удалось соединиться с COREZ ({адрес}): {exc}', None

    if ответ.status_code == 404:
        return False, f'Соревнование не найдено в COREZ (source_id={competition_source_id}).', None
    if ответ.status_code == 401:
        return False, 'COREZ отклонил запрос: неверный COREZ_API_KEY.', None
    if ответ.status_code != 200:
        return False, f'COREZ ответил ошибкой {ответ.status_code}: {ответ.text[:200]}', None

    данные = ответ.json()
    return True, 'Заявка отправлена в COREZ.', данные.get('application_id')


def обновить_заявку_команды(application, competition_source_id, corez_application_id):
    """Обновляет уже отправленную ранее заявку команды в COREZ (повторное
    нажатие «Отправить в COREZ» после редактирования). Возвращает
    (успех, сообщение)."""
    ключ = _ключ()
    if not ключ:
        return False, 'COREZ_API_KEY не задан в .env — см. .env.example'

    адрес = _адрес()
    try:
        ответ = requests.put(
            f'{адрес}/api/competitions/{competition_source_id}/applications/{corez_application_id}',
            json=_собрать_данные(application),
            headers={'X-API-Key': ключ},
            timeout=10,
        )
    except requests.RequestException as exc:
        return False, f'Не удалось соединиться с COREZ ({адрес}): {exc}'

    if ответ.status_code == 404:
        return False, 'Заявка не найдена в COREZ (возможно, была удалена там) — отправьте как новую.'
    if ответ.status_code == 401:
        return False, 'COREZ отклонил запрос: неверный COREZ_API_KEY.'
    if ответ.status_code != 200:
        return False, f'COREZ ответил ошибкой {ответ.status_code}: {ответ.text[:200]}'

    return True, 'Заявка обновлена в COREZ.'
