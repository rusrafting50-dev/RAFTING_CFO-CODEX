"""Общие мелкие хелперы, не привязанные к конкретному blueprint'у."""
from werkzeug.utils import secure_filename


def safe_upload_filename(original_filename):
    """secure_filename() из werkzeug вырезает все не-ASCII символы — для
    файла, чьё имя целиком на кириллице (обычный случай для загружаемых
    здесь документов/логотипов), это стирает не только название, но и
    точку-разделитель перед расширением, если оно осталось единственной
    ASCII-частью строки ("Международные правила....pdf" -> "pdf" без
    точки). Без точки в сохранённом имени браузер не может определить
    тип файла ни для иконки на сайте, ни при отдаче файла — Flask отдаёт
    его как application/octet-stream, и вместо открытия файл скачивается.

    Расширение и имя обрабатываются отдельно и всегда собираются обратно
    через точку, поэтому её потеря исключена."""
    base, ext = original_filename.rsplit('.', 1) if '.' in original_filename else (original_filename, '')
    safe_base = secure_filename(base) or 'file'
    safe_ext = secure_filename(ext).lower()
    return f'{safe_base}.{safe_ext}' if safe_ext else safe_base
