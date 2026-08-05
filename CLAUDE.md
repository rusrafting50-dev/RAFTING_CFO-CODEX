# CLAUDE.md — Проект RAFTING_SITE

## Что это за проект

Flask веб-сайт федерации рафтинга Центрального федерального округа.
Трёхуровневая структура: ЦФО → Региональная федерация → Местное отделение / Спортивный клуб.
Данные поступают автоматически из трёх внутренних проектов через общую SQLite базу данных.

---

## Источники данных

| Проект | Что поставляет на сайт |
|---|---|
| **COREZ** | Соревнования, календарный план, протоколы, результаты, составы ГСК |
| **REGTEAM_RAFTING** | Список сборной команды, спортсмены, тренеры |
| **SPORTS_REFEREE** | Спортивные судьи, семинары судей, составы коллегий |

Каждый проект пишет данные в **общую базу** `shared.db` которую читает сайт.
Сайт не редактирует данные напрямую — только отображает.

---

## Стек

- **Python 3.11+**
- **Flask** — веб-фреймворк
- **SQLAlchemy** — ORM для SQLite
- **Bootstrap 5** (CDN) — интерфейс
- **Jinja2** — шаблоны
- **SQLite** — база данных (`shared.db`)
- **Flask-Login** — авторизация

---

## Структура проекта

```
RAFTING_SITE/
├── CLAUDE.md
├── TASK.md
├── app.py                  # точка входа
├── models.py               # модели SQLAlchemy
├── auth.py                 # авторизация (Flask-Login)
├── routes/
│   ├── __init__.py
│   ├── main.py             # главная, новости
│   ├── competitions.py     # соревнования
│   ├── team.py             # сборная команда
│   ├── referees.py         # судьи
│   ├── events.py           # мероприятия (семинары)
│   ├── federation.py       # о федерации, структура
│   ├── documents.py        # нормативные документы
│   ├── regions.py          # региональные федерации ЦФО
│   ├── admin.py            # панель управления
│   └── api.py              # API для приёма данных от COREZ/REGTEAM/SPORTS_REFEREE
├── templates/
│   ├── base.html           # базовый шаблон с навигацией
│   ├── main/
│   │   ├── index.html      # главная страница
│   │   └── news.html       # новости
│   ├── competitions/
│   │   ├── calendar.html   # календарный план
│   │   ├── list.html       # список соревнований
│   │   └── detail.html     # страница соревнования
│   ├── team/
│   │   └── list.html       # список сборной
│   ├── referees/
│   │   └── list.html       # список судей
│   ├── events/
│   │   ├── list.html       # список мероприятий
│   │   └── detail.html     # страница мероприятия
│   ├── federation/
│   │   ├── about.html      # о федерации
│   │   └── structure.html  # структура
│   ├── documents/
│   │   └── list.html       # нормативные документы
│   ├── regions/
│   │   └── list.html       # региональные федерации
│   └── admin/
│       ├── login.html      # вход
│       └── dashboard.html  # панель управления
├── static/
│   ├── css/style.css
│   ├── js/main.js
│   └── uploads/            # загружаемые файлы (документы, фото)
├── requirements.txt
└── 1_Запуск.bat
```

---

## Модели базы данных (models.py)

### News (новости)
| Поле | Тип | Описание |
|---|---|---|
| id | Integer PK | |
| title | String | Заголовок |
| content | Text | Содержание |
| category | String | соревнование / мероприятие / федерация / регион |
| level | String | цфо / регион / отделение / клуб |
| published_at | DateTime | Дата публикации |
| is_published | Boolean | Опубликовано |
| created_by | Integer FK→User | |

### Competition (соревнования) — из COREZ
| Поле | Тип | Описание |
|---|---|---|
| id | Integer PK | |
| name | String | Наименование соревнований |
| comp_type | String | официальные спортивные / физкультурные |
| level | String | цфо / регион / отделение |
| start_date | Date | Дата начала |
| end_date | Date | Дата окончания |
| location | String | Место проведения |
| status | String | анонс / идёт / завершены |
| source_id | Integer | ID в базе COREZ |

### CompetitionDocument (документы соревнования)
| Поле | Тип | Описание |
|---|---|---|
| id | Integer PK | |
| competition_id | FK→Competition | |
| doc_type | String | положение / регламент / состав_гск / расписание / заявки / стартовый_протокол / протокол_результатов |
| title | String | Название документа |
| file_path | String | Путь к файлу |
| uploaded_at | DateTime | |

### Athlete (спортсмены и тренеры) — из REGTEAM_RAFTING
| Поле | Тип | Описание |
|---|---|---|
| id | Integer PK | |
| full_name | String | ФИО |
| role | String | спортсмен / тренер |
| discipline | String | Дисциплина |
| rank | String | Разряд / звание |
| organization | String | Организация |
| territory | String | Территория |
| national_team | String | Состав сборной РФ |
| source_id | Integer | ID в базе REGTEAM_RAFTING |

### Referee (судьи) — из SPORTS_REFEREE
| Поле | Тип | Описание |
|---|---|---|
| id | Integer PK | |
| full_name | String | ФИО |
| category | String | Категория (всероссийская и т.д.) |
| disciplines | String | Дисциплины |
| territory | String | Территория |
| organization | String | Организация |
| source_id | Integer | ID в базе SPORTS_REFEREE |

### Event (мероприятия — семинары)
| Поле | Тип | Описание |
|---|---|---|
| id | Integer PK | |
| name | String | Наименование |
| event_type | String | семинар_судей / семинар_тренеров / семинар_руководителей |
| start_date | Date | |
| end_date | Date | |
| location | String | |
| status | String | анонс / идёт / завершён |
| source_id | Integer | ID в базе SPORTS_REFEREE |

### Document (нормативные документы)
| Поле | Тип | Описание |
|---|---|---|
| id | Integer PK | |
| title | String | Название |
| doc_category | String | федеральный / региональный / wrf / фрр / федерация |
| file_path | String | Путь к файлу |
| level | String | цфо / регион |
| uploaded_at | DateTime | |

### User (пользователи)
| Поле | Тип | Описание |
|---|---|---|
| id | Integer PK | |
| username | String | Логин |
| password_hash | String | Хэш пароля |
| role | String | admin / editor / viewer |
| is_active | Boolean | |

### FederationMember (состав органов федерации)
| Поле | Тип | Описание |
|---|---|---|
| id | Integer PK | |
| full_name | String | ФИО |
| position | String | Должность |
| body | String | исполком / коллегия_судей / тренерский_совет / комитет_представителей |
| level | String | цфо / регион |
| photo_path | String | Фото |
| contacts | String | Контакты |

### RegionalFederation (региональные федерации ЦФО)
| Поле | Тип | Описание |
|---|---|---|
| id | Integer PK | |
| name | String | Название региональной федерации |
| logo_path | String | Логотип (выводится в круге на карточке) |

---

## API для синхронизации (routes/api.py)

Внутренние проекты отправляют данные через REST API:

```
POST /api/sync/competitions     # COREZ → соревнования
POST /api/sync/athletes         # REGTEAM_RAFTING → спортсмены
POST /api/sync/referees         # SPORTS_REFEREE → судьи
POST /api/sync/events           # SPORTS_REFEREE → мероприятия
```

Все запросы защищены API-ключом в заголовке `X-API-Key`.
API-ключ хранится в `.env` файле.

---

## Навигация сайта

### Главное меню
- **Новости**
- **Региональные федерации** → список федераций субъектов ЦФО
- **Соревнования** → Календарный план / Текущие / Архив
- **Спортсмены и тренеры** → Члены сборной РФ
- **Судьи** → Всероссийская категория
- **Нормативные документы**
- **Оборудование и снаряжение**
- **Мероприятия** → Семинары судей / Семинары тренеров
- **Представители ЦФО в ФРР**

### Уровни сайта
Сайт имеет три уровня — переключаются через поддомен или путь:
- `/` — уровень ЦФО
- `/region/<slug>` — уровень региональной федерации
- `/branch/<slug>` — уровень местного отделения

---

## Авторизация

- Публичная часть — без входа
- Панель администратора `/admin` — требует входа
- Роли: `admin` (полный доступ), `editor` (публикация новостей и документов), `viewer` (только просмотр)
- Вход через `/admin/login`

---

## Страница соревнования

Каждое соревнование имеет подстраницы:
- Информация (анонс, место, даты)
- Выписка из Положения
- Регламент
- Состав ГСК
- Расписание тренировок
- График комиссии по допуску
- Регламент жеребьёвки и старта
- Протокол совещания ГСК
- Справка о составе субъектов
- Справка о составе судейской коллегии
- Заявки
- Стартовые протоколы
- Протоколы результатов

---

## Запуск

```bat
@echo off
cd /d "D:\Projects Claude Code\RAFTING_SITE"
echo [1/3] Git pull...
git pull origin main
echo [2/3] pip install...
pip install -r requirements.txt --quiet
echo [3/3] Start Flask...
start http://localhost:5003
python app.py
pause
```

Flask запускается на порту **5003** (чтобы не конфликтовать с другими проектами).

---

## requirements.txt

```
flask>=3.0
flask-sqlalchemy>=3.1
flask-login>=0.6
python-dotenv>=1.0
werkzeug>=3.0
```

---

## Важные особенности

- Сайт только читает данные из внутренних проектов через API — не редактирует
- Документы (PDF, DOCX) загружаются в `static/uploads/` и доступны для скачивания
- Новости можно добавлять прямо на сайте через панель администратора
- Члены органов федерации (исполком, коллегия судей и т.д.) вводятся вручную через админку
- Нормативные документы загружаются вручную через админку
- Все текстовые страницы (о федерации, устав, контакты) редактируются через админку

---

## Оформление (стиль rfs.ru)

Ориентир — сайт rfs.ru. Реализовать следующие элементы:

### Шапка (динамическая)
- В обычном состоянии: высокая (~90px), тёмный фон (#1a1a2e), крупный логотип и название
- При прокрутке страницы вниз (>50px): шапка уменьшается (~55px), логотип меньше
- Шапка прилипает к верху экрана (position: sticky, top: 0)
- Плавный переход через CSS transition (height, padding — 0.3s ease)
- Реализация через JavaScript: слушать событие window scroll, добавлять/убирать CSS-класс `.scrolled` на элемент header
- Пример:
```javascript
window.addEventListener('scroll', function() {
    const header = document.querySelector('header');
    if (window.scrollY > 50) {
        header.classList.add('scrolled');
    } else {
        header.classList.remove('scrolled');
    }
});
```
```css
header {
    height: 90px;
    transition: height 0.3s ease, padding 0.3s ease;
    position: sticky;
    top: 0;
    z-index: 1000;
    background: #1a1a2e;
}
header.scrolled {
    height: 55px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
}
header.scrolled .logo {
    height: 35px;
    transition: height 0.3s ease;
}
```

### Цветовая схема
- Основной тёмный: `#1a1a2e`
- Акцентный синий: `#0066cc`
- Фон страницы: `#f5f5f5`
- Белые карточки с тенью: `box-shadow: 0 2px 8px rgba(0,0,0,0.1)`

### Главная страница
- Широкий баннер-герой под шапкой (фото реки + рафт + название федерации)
- Сетка карточек новостей (3 колонки на desktop, 1 на mobile)
- Карточка новости: фото сверху, дата серым, заголовок жирный, анонс 2-3 строки
- Блок «Ближайшие соревнования» — горизонтальный список с датами

### Навигационное меню
- Горизонтальное в шапке, на hover — выпадающий подраздел
- На мобильном — иконка гамбургер, меню выезжает сбоку

### Страница соревнования
- Горизонтальные вкладки (tabs) для каждого документа
- Таблицы результатов: чередование строк (#fff / #f8f8f8), заголовки с тёмным фоном

### Подвал
- Тёмный фон (#1a1a2e), белый текст
- 4 колонки ссылок
- Строка копирайта внизу

### Шрифт
- `font-family: 'Roboto', Arial, Helvetica, sans-serif` — на rfs.ru используется Roboto
  (проверено через DevTools), подключается через Google Fonts; Arial/Helvetica — запасной
  вариант, если шрифт не загрузился

### Адаптивность
- Bootstrap 5 grid
- На мобильном меню — гамбургер (Bootstrap navbar-toggler)
- Карточки новостей: 3 колонки (desktop) → 2 (планшет) → 1 (mobile)
