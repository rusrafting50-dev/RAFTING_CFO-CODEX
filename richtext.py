"""Санитизация HTML из редактора форматированного текста панели
управления (см. static/js/rich_text_editor.js) — тексты вроде
RegionalFederation.intro_text/goals_text, Club.*_text, News.content
хранятся уже как HTML (заголовки, выравнивание, отступ абзаца) и
выводятся на публичных страницах через фильтр |richtext (см. app.py) с
безопасным выводом без экранирования. bleach.clean режет всё, кроме
заданного здесь набора тегов/стилей — редактор ничего больше и не
производит, но значения нужно перепроверять на сервере, а не доверять
тому, что пришло в POST-запросе."""
import re

import bleach

ALLOWED_TAGS = frozenset({'p', 'h2', 'h3', 'br'})

# Инлайновые стили, которые реально расставляет тулбар редактора —
# выравнивание и отступ фиксированными шагами (см. INDENT_STEP/MAX_INDENT
# в rich_text_editor.js). Любая другая CSS-декларация (в том числе
# background/url() и т.п.) отбрасывается.
_ALLOWED_STYLE_DECLARATION = re.compile(
    r'^(text-align:\s*(left|center|right)|margin-left:\s*(0|40|80|120|160)px)$'
)


class _AlignIndentCSSSanitizer:
    """Простой объект с sanitize_css (интерфейс, который bleach.Cleaner
    ожидает от css_sanitizer) — без установки отдельного пакета
    tinycss2, который bleach.css_sanitizer.CSSSanitizer тянет за собой
    для куда более широкой задачи (произвольный CSS), чем нужна здесь
    (ровно два свойства с фиксированными значениями)."""

    def sanitize_css(self, style):
        declarations = [d.strip() for d in style.split(';') if d.strip()]
        valid = [d for d in declarations if _ALLOWED_STYLE_DECLARATION.match(d)]
        return '; '.join(valid)


_cleaner = bleach.sanitizer.Cleaner(
    tags=ALLOWED_TAGS, attributes={'*': ['style']},
    css_sanitizer=_AlignIndentCSSSanitizer(), strip=True, strip_comments=True,
)


def sanitize_rich_text(html):
    """None/пустая строка остаются None — как и раньше у текстовых полей
    (админка сохраняет request.form.get(...).strip() or None)."""
    if not html or not html.strip():
        return None
    cleaned = _cleaner.clean(html.strip())
    # style="" — валидных деклараций не нашлось (css_sanitizer вернул
    # пустую строку, но сам атрибут при непустом исходном значении не
    # удаляется) — косметика, чтобы в БД не оседал мусорный пустой
    # атрибут.
    cleaned = cleaned.replace(' style=""', '')
    return cleaned or None
