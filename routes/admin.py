"""Панель администратора: вход, дашборд, управление контентом."""
import os
import re
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint, current_app, flash, redirect, render_template,
    request, url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from models import (
    Athlete, Banner, Competition, CompetitionDocument, Document, DocumentCategory, DocumentSection,
    Event, FederationMember, FederationRegistrationRequest, MediaAlbum, MediaAlbumPhoto, MediaVideo,
    News, NewsCategory, NewsImage, NewsLevel, PartnerLogo, PasswordResetRequest, Referee,
    RegionalFederation, SeminarApplicationSubmission, SyncLog, User, db,
)
from sync_to_referee import отправить_заявку, обновить_заявку

bp = Blueprint('admin', __name__)


@bp.after_request
def no_cache(response):
    """Панель администратора не должна отдавать страницы из browser-кэша
    (в т.ч. bfcache при переходе назад/вперёд) — иначе после сохранения
    формы (например, названия альбома) можно случайно увидеть старые
    данные и решить, что изменение не сохранилось."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return response


ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'docx'}
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
SYNC_SOURCES = ['COREZ', 'REGTEAM_RAFTING', 'SPORTS_REFEREE']

BODY_CHOICES = ['исполком', 'коллегия_судей', 'тренерский_совет', 'комитет_представителей']
ROLE_CHOICES = ['admin', 'editor', 'viewer', 'region_rep']

YOUTUBE_ID_RE = re.compile(
    r'(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})'
)


def extract_youtube_id(url):
    match = YOUTUBE_ID_RE.search(url or '')
    return match.group(1) if match else None


def youtube_thumbnail_url(video_id):
    # mqdefault.jpg — честные пропорции 16:9 и есть у любого видео. У
    # hqdefault.jpg (использовался раньше) канва 4:3 — для 16:9 видео
    # это чёрные полосы сверху/снизу, выпилить их обрезкой поля нельзя,
    # т.к. они запечены в саму картинку.
    return f'https://img.youtube.com/vi/{video_id}/mqdefault.jpg'


def news_category_choices():
    return [c.name for c in NewsCategory.query.order_by(NewsCategory.name).all()]


def news_level_choices():
    return [lvl.name for lvl in NewsLevel.query.order_by(NewsLevel.name).all()]
# Разделы панели, доступ к которым назначается сотруднику индивидуально
# (роль admin получает их все автоматически, см. User.can_access).
SECTION_CHOICES = [
    ('news', 'Новости'),
    ('competitions', 'Соревнования'),
    ('documents', 'Документы'),
    ('members', 'Члены органов'),
    ('regions', 'Регионы ЦФО'),
    ('banners', 'Баннеры'),
    ('media', 'Медиа'),
    ('partners', 'Логотипы партнёров'),
    ('sync', 'Синхронизация'),
]
SECTION_KEYS = [key for key, _ in SECTION_CHOICES]

# Каталог мест на сайте, куда можно поместить баннер — при добавлении
# новой рекламной позиции на другой странице достаточно дописать пару сюда,
# без изменений в модели БД (см. render в шаблоне соответствующей страницы).
BANNER_PAGE_CHOICES = [
    ('main.index', 'Главная'),
]
BANNER_POSITION_CHOICES = [
    ('news_sidebar', 'Колонка рядом с новостями'),
]
COMPETITION_DOC_TYPE_CHOICES = [
    'положение', 'регламент', 'состав_гск', 'расписание',
    'график_допуска', 'регламент_жеребьёвки', 'протокол_совещания_гск',
    'справка_о_субъектах', 'справка_о_судьях', 'заявки',
    'стартовый_протокол', 'протокол_результатов',
]


def roles_required(*roles):
    """Ограничивает доступ к маршруту указанными ролями (предполагает вход в систему)."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                flash('У вас недостаточно прав для этого действия.', 'error')
                return redirect(url_for('admin.dashboard'))
            return view(*args, **kwargs)
        return login_required(wrapped)
    return decorator


def section_required(section):
    """Ограничивает доступ к разделу панели — по индивидуальному списку
    разрешённых разделов сотрудника (роль admin проходит всегда)."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.can_access(section):
                flash('У вас нет доступа к этому разделу панели.', 'error')
                return redirect(url_for('admin.dashboard'))
            return view(*args, **kwargs)
        return login_required(wrapped)
    return decorator


def is_last_active_admin(user):
    """True, если это единственный активный admin — такого нельзя разжаловать/отключить."""
    if user.role != 'admin' or not user.is_active:
        return False
    other_active_admins = User.query.filter(
        User.role == 'admin', User.is_active.is_(True), User.id != user.id,
    ).count()
    return other_active_admins == 0


def allowed_document(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_DOCUMENT_EXTENSIONS


def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_upload(file):
    """Сохраняет файл в UPLOAD_FOLDER под уникальным именем, возвращает путь
    относительно static/ (как хранится в *.file_path / *.image_path)."""
    filename = secure_filename(file.filename)
    unique_name = f"{datetime.utcnow():%Y%m%d%H%M%S}_{filename}"
    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, unique_name))
    return f"uploads/{unique_name}"


def latest_sync_by_source():
    return {
        source: (
            SyncLog.query.filter_by(source=source)
            .order_by(SyncLog.synced_at.desc())
            .first()
        )
        for source in SYNC_SOURCES
    }


# ---------- Вход / выход ----------

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            if not user.is_active:
                flash('Учётная запись отключена.', 'error')
                return render_template('admin/login.html')
            login_user(user)
            flash('Вы успешно вошли в систему.', 'success')
            return redirect(request.args.get('next') or url_for('admin.dashboard'))

        flash('Неверный логин или пароль.', 'error')

    return render_template('admin/login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'success')
    return redirect(url_for('admin.login'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        short_name = request.form.get('short_name', '').strip()
        leader_full_name = request.form.get('leader_full_name', '').strip()
        leader_position = request.form.get('leader_position', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        if not full_name or not leader_full_name or not email or not password:
            flash('Заполните все обязательные поля.', 'error')
            return render_template('admin/register.html', form=request.form)

        if password != password2:
            flash('Пароли не совпадают.', 'error')
            return render_template('admin/register.html', form=request.form)

        if User.query.filter_by(username=email).first():
            flash('Пользователь с таким email уже зарегистрирован.', 'error')
            return render_template('admin/register.html', form=request.form)

        if FederationRegistrationRequest.query.filter_by(email=email, status='pending').first():
            flash('Заявка с таким email уже подана и ожидает проверки.', 'error')
            return render_template('admin/register.html', form=request.form)

        db.session.add(FederationRegistrationRequest(
            full_name=full_name,
            short_name=short_name or None,
            leader_full_name=leader_full_name,
            leader_position=leader_position or None,
            phone=phone or None,
            email=email,
            password_hash=generate_password_hash(password),
        ))
        db.session.commit()

        flash('Заявка отправлена. После проверки данных на почту придёт пароль для входа на сайт.', 'success')
        return redirect(url_for('admin.login'))

    return render_template('admin/register.html', form=None)


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email', '').strip()
        if not username_or_email:
            flash('Укажите логин или email.', 'error')
            return render_template('admin/forgot_password.html')

        db.session.add(PasswordResetRequest(username_or_email=username_or_email))
        db.session.commit()

        flash('Заявка принята. Администратор свяжется с вами и сообщит новый пароль.', 'success')
        return redirect(url_for('admin.login'))

    return render_template('admin/forgot_password.html')


# ---------- Дашборд ----------

@bp.route('/')
@login_required
def dashboard():
    stats = {
        'news': News.query.count(),
        'competitions': Competition.query.count(),
        'referees': Referee.query.count(),
        'athletes': Athlete.query.count(),
    }
    return render_template(
        'admin/dashboard.html', active='dashboard',
        stats=stats, latest_syncs=latest_sync_by_source(),
    )


# ---------- Новости ----------

@bp.route('/news')
@section_required('news')
def news_list():
    items = News.query.order_by(News.published_at.desc()).all()
    return render_template('admin/news_list.html', active='news', news_items=items)


@bp.route('/news/new', methods=['GET', 'POST'])
@section_required('news')
@roles_required('admin', 'editor')
def news_new():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        description = request.form.get('description', '').strip()
        image = request.files.get('image')
        gallery_files = [f for f in request.files.getlist('gallery_images') if f and f.filename]

        if not title or not content:
            flash('Заголовок и текст новости обязательны.', 'error')
            return render_template(
                'admin/news_form.html', active='news', news=None,
                category_choices=news_category_choices(), level_choices=news_level_choices(),
            )

        bad_images = [f for f in [image, *gallery_files] if f and f.filename and not allowed_image(f.filename)]
        if bad_images:
            flash('Допустимые форматы фотографии: JPG, PNG, WEBP.', 'error')
            return render_template(
                'admin/news_form.html', active='news', news=None,
                category_choices=news_category_choices(), level_choices=news_level_choices(),
            )

        news_item = News(
            title=title,
            content=content,
            description=description or None,
            category=request.form.get('category') or None,
            level=request.form.get('level') or None,
            photo_author=request.form.get('photo_author', '').strip() or None,
            organization=request.form.get('organization', '').strip() or None,
            is_published=bool(request.form.get('is_published')),
            created_by=current_user.id,
            image_path=save_upload(image) if image and image.filename else None,
        )
        db.session.add(news_item)
        for gallery_file in gallery_files:
            db.session.add(NewsImage(news=news_item, file_path=save_upload(gallery_file)))
        db.session.commit()
        flash('Новость создана.', 'success')
        return redirect(url_for('admin.news_list'))

    return render_template(
        'admin/news_form.html', active='news', news=None,
        category_choices=news_category_choices(), level_choices=news_level_choices(),
    )


@bp.route('/news/<int:news_id>/edit', methods=['GET', 'POST'])
@section_required('news')
@roles_required('admin', 'editor')
def news_edit(news_id):
    news_item = News.query.get_or_404(news_id)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        description = request.form.get('description', '').strip()
        image = request.files.get('image')
        gallery_files = [f for f in request.files.getlist('gallery_images') if f and f.filename]

        if not title or not content:
            flash('Заголовок и текст новости обязательны.', 'error')
            return render_template(
                'admin/news_form.html', active='news', news=news_item,
                category_choices=news_category_choices(), level_choices=news_level_choices(),
            )

        bad_images = [f for f in [image, *gallery_files] if f and f.filename and not allowed_image(f.filename)]
        if bad_images:
            flash('Допустимые форматы фотографии: JPG, PNG, WEBP.', 'error')
            return render_template(
                'admin/news_form.html', active='news', news=news_item,
                category_choices=news_category_choices(), level_choices=news_level_choices(),
            )

        news_item.title = title
        news_item.content = content
        news_item.description = description or None
        news_item.category = request.form.get('category') or None
        news_item.level = request.form.get('level') or None
        news_item.photo_author = request.form.get('photo_author', '').strip() or None
        news_item.organization = request.form.get('organization', '').strip() or None
        news_item.is_published = bool(request.form.get('is_published'))
        if image and image.filename:
            news_item.image_path = save_upload(image)
        for gallery_file in gallery_files:
            db.session.add(NewsImage(news=news_item, file_path=save_upload(gallery_file)))
        db.session.commit()
        flash('Новость обновлена.', 'success')
        return redirect(url_for('admin.news_list'))

    return render_template(
        'admin/news_form.html', active='news', news=news_item,
        category_choices=news_category_choices(), level_choices=news_level_choices(),
    )


@bp.route('/news/<int:news_id>/delete', methods=['POST'])
@section_required('news')
@roles_required('admin', 'editor')
def news_delete(news_id):
    news_item = News.query.get_or_404(news_id)
    db.session.delete(news_item)
    db.session.commit()
    flash('Новость удалена.', 'success')
    return redirect(url_for('admin.news_list'))


@bp.route('/news/<int:news_id>/images/<int:image_id>/delete', methods=['POST'])
@section_required('news')
@roles_required('admin', 'editor')
def news_image_delete(news_id, image_id):
    image = NewsImage.query.filter_by(id=image_id, news_id=news_id).first_or_404()
    db.session.delete(image)
    db.session.commit()
    flash('Фото удалено.', 'success')
    return redirect(url_for('admin.news_edit', news_id=news_id))


@bp.route('/news/<int:news_id>/toggle-publish', methods=['POST'])
@section_required('news')
@roles_required('admin', 'editor')
def news_toggle_publish(news_id):
    news_item = News.query.get_or_404(news_id)
    news_item.is_published = not news_item.is_published
    db.session.commit()
    flash('Публикация новости обновлена.', 'success')
    return redirect(url_for('admin.news_list'))


# ---------- Категории и уровни новостей ----------

@bp.route('/news/taxonomy')
@section_required('news')
def news_taxonomy():
    categories = NewsCategory.query.order_by(NewsCategory.name).all()
    levels = NewsLevel.query.order_by(NewsLevel.name).all()
    return render_template(
        'admin/news_taxonomy.html', active='news', categories=categories, levels=levels,
    )


@bp.route('/news/taxonomy/categories/new', methods=['POST'])
@section_required('news')
@roles_required('admin', 'editor')
def news_category_new():
    name = request.form.get('name', '').strip()
    # Сравнение регистронезависимо и в Python: SQLite lower() не умеет
    # сворачивать регистр кириллицы, поэтому SQL-фильтр по func.lower()
    # пропустил бы дубликат вида "регион"/"Регион".
    if not name:
        flash('Название категории обязательно.', 'error')
    elif any(c.name.lower() == name.lower() for c in NewsCategory.query.all()):
        flash('Такая категория уже есть.', 'error')
    else:
        db.session.add(NewsCategory(name=name))
        db.session.commit()
        flash('Категория добавлена.', 'success')
    return redirect(url_for('admin.news_taxonomy'))


@bp.route('/news/taxonomy/categories/<int:category_id>/delete', methods=['POST'])
@section_required('news')
@roles_required('admin', 'editor')
def news_category_delete(category_id):
    category = NewsCategory.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    flash('Категория удалена. Уже опубликованные новости с этим значением не изменятся.', 'success')
    return redirect(url_for('admin.news_taxonomy'))


@bp.route('/news/taxonomy/levels/new', methods=['POST'])
@section_required('news')
@roles_required('admin', 'editor')
def news_level_new():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Название уровня обязательно.', 'error')
    elif any(lvl.name.lower() == name.lower() for lvl in NewsLevel.query.all()):
        flash('Такой уровень уже есть.', 'error')
    else:
        db.session.add(NewsLevel(name=name))
        db.session.commit()
        flash('Уровень добавлен.', 'success')
    return redirect(url_for('admin.news_taxonomy'))


@bp.route('/news/taxonomy/levels/<int:level_id>/delete', methods=['POST'])
@section_required('news')
@roles_required('admin', 'editor')
def news_level_delete(level_id):
    level = NewsLevel.query.get_or_404(level_id)
    db.session.delete(level)
    db.session.commit()
    flash('Уровень удалён. Уже опубликованные новости с этим значением не изменятся.', 'success')
    return redirect(url_for('admin.news_taxonomy'))


# ---------- Документы ----------

def document_category_choices():
    return [c.name for c in DocumentCategory.query.order_by(DocumentCategory.name).all()]


def document_sections_by_category():
    return {
        category.name: [{'id': s.id, 'name': s.name} for s in category.sections]
        for category in DocumentCategory.query.order_by(DocumentCategory.name).all()
    }


@bp.route('/documents')
@section_required('documents')
def documents_list():
    items = Document.query.order_by(Document.doc_category, Document.title).all()
    return render_template('admin/documents_list.html', active='documents', documents=items)


@bp.route('/documents/taxonomy')
@section_required('documents')
def document_taxonomy():
    categories = DocumentCategory.query.order_by(DocumentCategory.name).all()
    return render_template('admin/document_taxonomy.html', active='documents', categories=categories)


@bp.route('/documents/taxonomy/categories/new', methods=['POST'])
@section_required('documents')
@roles_required('admin', 'editor')
def document_category_new():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Название категории обязательно.', 'error')
    elif any(c.name.lower() == name.lower() for c in DocumentCategory.query.all()):
        flash('Такая категория уже есть.', 'error')
    else:
        db.session.add(DocumentCategory(name=name))
        db.session.commit()
        flash('Категория добавлена.', 'success')
    return redirect(url_for('admin.document_taxonomy'))


@bp.route('/documents/taxonomy/categories/<int:category_id>/delete', methods=['POST'])
@section_required('documents')
@roles_required('admin', 'editor')
def document_category_delete(category_id):
    category = DocumentCategory.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    flash('Категория удалена. Уже загруженные документы с этим значением не изменятся.', 'success')
    return redirect(url_for('admin.document_taxonomy'))


@bp.route('/documents/taxonomy/categories/<int:category_id>/sections/new', methods=['POST'])
@section_required('documents')
@roles_required('admin', 'editor')
def document_section_new(category_id):
    category = DocumentCategory.query.get_or_404(category_id)
    name = request.form.get('name', '').strip()
    if not name:
        flash('Название раздела обязательно.', 'error')
    elif any(s.name.lower() == name.lower() for s in category.sections):
        flash('Такой раздел в этой категории уже есть.', 'error')
    else:
        db.session.add(DocumentSection(category_id=category.id, name=name))
        db.session.commit()
        flash('Раздел добавлен.', 'success')
    return redirect(url_for('admin.document_taxonomy'))


@bp.route('/documents/taxonomy/sections/<int:section_id>/delete', methods=['POST'])
@section_required('documents')
@roles_required('admin', 'editor')
def document_section_delete(section_id):
    section = DocumentSection.query.get_or_404(section_id)
    db.session.delete(section)
    db.session.commit()
    flash('Раздел удалён. Уже загруженные документы с этим значением не изменятся.', 'success')
    return redirect(url_for('admin.document_taxonomy'))


@bp.route('/documents/new', methods=['GET', 'POST'])
@section_required('documents')
@roles_required('admin', 'editor')
def documents_new():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        file = request.files.get('file')

        if not title or not file or file.filename == '':
            flash('Название и файл документа обязательны.', 'error')
            return render_template(
                'admin/document_form.html', active='documents',
                category_choices=document_category_choices(), sections_by_category=document_sections_by_category(),
            )

        if not allowed_document(file.filename):
            flash('Допустимые форматы файлов: PDF, DOCX.', 'error')
            return render_template(
                'admin/document_form.html', active='documents',
                category_choices=document_category_choices(), sections_by_category=document_sections_by_category(),
            )

        filename = secure_filename(file.filename)
        unique_name = f"{datetime.utcnow():%Y%m%d%H%M%S}_{filename}"
        upload_dir = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, unique_name))

        document = Document(
            title=title,
            doc_category=request.form.get('doc_category') or None,
            section_id=request.form.get('section_id', type=int),
            file_path=f"uploads/{unique_name}",
        )
        db.session.add(document)
        db.session.commit()
        flash('Документ загружен.', 'success')
        return redirect(url_for('admin.documents_list'))

    return render_template(
        'admin/document_form.html', active='documents',
        category_choices=document_category_choices(), sections_by_category=document_sections_by_category(),
    )


@bp.route('/documents/<int:document_id>/edit', methods=['GET', 'POST'])
@section_required('documents')
@roles_required('admin', 'editor')
def documents_edit(document_id):
    document = Document.query.get_or_404(document_id)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        file = request.files.get('file')

        if not title:
            flash('Название документа обязательно.', 'error')
            return render_template(
                'admin/document_form.html', active='documents', document=document,
                category_choices=document_category_choices(), sections_by_category=document_sections_by_category(),
            )

        if file and file.filename:
            if not allowed_document(file.filename):
                flash('Допустимые форматы файлов: PDF, DOCX.', 'error')
                return render_template(
                    'admin/document_form.html', active='documents', document=document,
                    category_choices=document_category_choices(), sections_by_category=document_sections_by_category(),
                )

            filename = secure_filename(file.filename)
            unique_name = f"{datetime.utcnow():%Y%m%d%H%M%S}_{filename}"
            upload_dir = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, unique_name))

            old_path = os.path.join(current_app.root_path, 'static', document.file_path)
            if os.path.exists(old_path):
                os.remove(old_path)
            document.file_path = f"uploads/{unique_name}"

        document.title = title
        document.doc_category = request.form.get('doc_category') or None
        document.section_id = request.form.get('section_id', type=int)
        db.session.commit()
        flash('Документ изменён.', 'success')
        return redirect(url_for('admin.documents_list'))

    return render_template(
        'admin/document_form.html', active='documents', document=document,
        category_choices=document_category_choices(), sections_by_category=document_sections_by_category(),
    )


@bp.route('/documents/<int:document_id>/delete', methods=['POST'])
@section_required('documents')
@roles_required('admin', 'editor')
def documents_delete(document_id):
    document = Document.query.get_or_404(document_id)
    file_path = os.path.join(current_app.root_path, 'static', document.file_path)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.session.delete(document)
    db.session.commit()
    flash('Документ удалён.', 'success')
    return redirect(url_for('admin.documents_list'))


# ---------- Документы соревнований ----------

@bp.route('/competitions')
@section_required('competitions')
def competitions_list():
    competitions = Competition.query.order_by(Competition.start_date.desc()).all()
    return render_template('admin/competitions_list.html', active='competitions', competitions=competitions)


@bp.route('/competitions/<int:competition_id>/documents')
@section_required('competitions')
def competition_documents(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    documents = (
        CompetitionDocument.query.filter_by(competition_id=competition_id)
        .order_by(CompetitionDocument.doc_type)
        .all()
    )
    return render_template(
        'admin/competition_documents.html', active='competitions',
        competition=competition, documents=documents,
        doc_type_choices=COMPETITION_DOC_TYPE_CHOICES,
    )


@bp.route('/competitions/<int:competition_id>/documents/new', methods=['POST'])
@section_required('competitions')
@roles_required('admin', 'editor')
def competition_document_new(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    doc_type = request.form.get('doc_type')
    title = request.form.get('title', '').strip()
    file = request.files.get('file')

    if doc_type not in COMPETITION_DOC_TYPE_CHOICES or not title or not file or file.filename == '':
        flash('Тип документа, название и файл обязательны.', 'error')
        return redirect(url_for('admin.competition_documents', competition_id=competition.id))

    if not allowed_document(file.filename):
        flash('Допустимые форматы файлов: PDF, DOCX.', 'error')
        return redirect(url_for('admin.competition_documents', competition_id=competition.id))

    filename = secure_filename(file.filename)
    unique_name = f"{datetime.utcnow():%Y%m%d%H%M%S}_{filename}"
    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, unique_name))

    document = CompetitionDocument(
        competition_id=competition.id,
        doc_type=doc_type,
        title=title,
        file_path=f"uploads/{unique_name}",
    )
    db.session.add(document)
    db.session.commit()
    flash('Документ соревнования загружен.', 'success')
    return redirect(url_for('admin.competition_documents', competition_id=competition.id))


@bp.route('/competitions/<int:competition_id>/documents/<int:document_id>/delete', methods=['POST'])
@section_required('competitions')
@roles_required('admin', 'editor')
def competition_document_delete(competition_id, document_id):
    document = CompetitionDocument.query.filter_by(
        id=document_id, competition_id=competition_id,
    ).first_or_404()

    if document.file_path:
        file_path = os.path.join(current_app.root_path, 'static', document.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(document)
    db.session.commit()
    flash('Документ удалён.', 'success')
    return redirect(url_for('admin.competition_documents', competition_id=competition_id))


# ---------- Члены органов федерации ----------

@bp.route('/members')
@section_required('members')
def members_list():
    members = FederationMember.query.order_by(FederationMember.body, FederationMember.full_name).all()
    return render_template('admin/members_list.html', active='members', members=members)


@bp.route('/members/new', methods=['GET', 'POST'])
@section_required('members')
@roles_required('admin')
def members_new():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        body = request.form.get('body') or None

        if not full_name or not body:
            flash('ФИО и орган федерации обязательны.', 'error')
            return render_template('admin/member_form.html', active='members', member=None, body_choices=BODY_CHOICES)

        member = FederationMember(
            full_name=full_name,
            position=request.form.get('position', '').strip(),
            body=body,
            level=request.form.get('level') or None,
            contacts=request.form.get('contacts', '').strip(),
        )
        db.session.add(member)
        db.session.commit()
        flash('Член органа федерации добавлен.', 'success')
        return redirect(url_for('admin.members_list'))

    return render_template('admin/member_form.html', active='members', member=None, body_choices=BODY_CHOICES)


@bp.route('/members/<int:member_id>/edit', methods=['GET', 'POST'])
@section_required('members')
@roles_required('admin')
def members_edit(member_id):
    member = FederationMember.query.get_or_404(member_id)

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        body = request.form.get('body') or None

        if not full_name or not body:
            flash('ФИО и орган федерации обязательны.', 'error')
            return render_template('admin/member_form.html', active='members', member=member, body_choices=BODY_CHOICES)

        member.full_name = full_name
        member.position = request.form.get('position', '').strip()
        member.body = body
        member.level = request.form.get('level') or None
        member.contacts = request.form.get('contacts', '').strip()
        db.session.commit()
        flash('Данные обновлены.', 'success')
        return redirect(url_for('admin.members_list'))

    return render_template('admin/member_form.html', active='members', member=member, body_choices=BODY_CHOICES)


@bp.route('/members/<int:member_id>/delete', methods=['POST'])
@section_required('members')
@roles_required('admin')
def members_delete(member_id):
    member = FederationMember.query.get_or_404(member_id)
    db.session.delete(member)
    db.session.commit()
    flash('Запись удалена.', 'success')
    return redirect(url_for('admin.members_list'))


# ---------- Региональные федерации ----------

@bp.route('/regions')
@section_required('regions')
def regions_list():
    regional_federations = RegionalFederation.query.order_by(RegionalFederation.name).all()
    return render_template('admin/regions_list.html', active='regions', regional_federations=regional_federations)


@bp.route('/regions/new', methods=['GET', 'POST'])
@section_required('regions')
@roles_required('admin', 'editor')
def regions_new():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        logo = request.files.get('logo')

        if not name:
            flash('Название федерации обязательно.', 'error')
            return render_template('admin/region_form.html', active='regions', region=None)

        if logo and logo.filename and not allowed_image(logo.filename):
            flash('Допустимые форматы логотипа: JPG, PNG, WEBP.', 'error')
            return render_template('admin/region_form.html', active='regions', region=None)

        region = RegionalFederation(
            name=name,
            logo_path=save_upload(logo) if logo and logo.filename else None,
        )
        db.session.add(region)
        db.session.commit()
        flash('Региональная федерация добавлена.', 'success')
        return redirect(url_for('admin.regions_list'))

    return render_template('admin/region_form.html', active='regions', region=None)


@bp.route('/regions/<int:region_id>/edit', methods=['GET', 'POST'])
@section_required('regions')
@roles_required('admin', 'editor')
def regions_edit(region_id):
    region = RegionalFederation.query.get_or_404(region_id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        logo = request.files.get('logo')

        if not name:
            flash('Название федерации обязательно.', 'error')
            return render_template('admin/region_form.html', active='regions', region=region)

        if logo and logo.filename and not allowed_image(logo.filename):
            flash('Допустимые форматы логотипа: JPG, PNG, WEBP.', 'error')
            return render_template('admin/region_form.html', active='regions', region=region)

        region.name = name
        if logo and logo.filename:
            region.logo_path = save_upload(logo)
        db.session.commit()
        flash('Данные обновлены.', 'success')
        return redirect(url_for('admin.regions_list'))

    return render_template('admin/region_form.html', active='regions', region=region)


@bp.route('/regions/<int:region_id>/delete', methods=['POST'])
@section_required('regions')
@roles_required('admin', 'editor')
def regions_delete(region_id):
    region = RegionalFederation.query.get_or_404(region_id)
    db.session.delete(region)
    db.session.commit()
    flash('Региональная федерация удалена.', 'success')
    return redirect(url_for('admin.regions_list'))


# ---------- Баннеры ----------

@bp.route('/banners')
@section_required('banners')
def banners_list():
    banners = Banner.query.order_by(Banner.page, Banner.position, Banner.sort_order).all()
    return render_template(
        'admin/banners_list.html', active='banners', banners=banners,
        page_choices=BANNER_PAGE_CHOICES, position_choices=BANNER_POSITION_CHOICES,
    )


@bp.route('/banners/new', methods=['GET', 'POST'])
@section_required('banners')
@roles_required('admin', 'editor')
def banners_new():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        page = request.form.get('page', '')
        position = request.form.get('position', '')
        link_url = request.form.get('link_url', '').strip()
        sort_order = request.form.get('sort_order', type=int) or 0
        image = request.files.get('image')

        page_keys = [key for key, _ in BANNER_PAGE_CHOICES]
        position_keys = [key for key, _ in BANNER_POSITION_CHOICES]

        if not title or page not in page_keys or position not in position_keys:
            flash('Заполните название и выберите страницу/место.', 'error')
            return render_template(
                'admin/banner_form.html', active='banners', banner=None,
                page_choices=BANNER_PAGE_CHOICES, position_choices=BANNER_POSITION_CHOICES,
            )

        if not image or not image.filename:
            flash('Изображение баннера обязательно.', 'error')
            return render_template(
                'admin/banner_form.html', active='banners', banner=None,
                page_choices=BANNER_PAGE_CHOICES, position_choices=BANNER_POSITION_CHOICES,
            )

        if not allowed_image(image.filename):
            flash('Допустимые форматы изображения: JPG, PNG, WEBP.', 'error')
            return render_template(
                'admin/banner_form.html', active='banners', banner=None,
                page_choices=BANNER_PAGE_CHOICES, position_choices=BANNER_POSITION_CHOICES,
            )

        banner = Banner(
            title=title,
            page=page,
            position=position,
            link_url=link_url or None,
            sort_order=sort_order,
            image_path=save_upload(image),
        )
        db.session.add(banner)
        db.session.commit()
        flash('Баннер добавлен.', 'success')
        return redirect(url_for('admin.banners_list'))

    return render_template(
        'admin/banner_form.html', active='banners', banner=None,
        page_choices=BANNER_PAGE_CHOICES, position_choices=BANNER_POSITION_CHOICES,
    )


@bp.route('/banners/<int:banner_id>/edit', methods=['GET', 'POST'])
@section_required('banners')
@roles_required('admin', 'editor')
def banners_edit(banner_id):
    banner = Banner.query.get_or_404(banner_id)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        page = request.form.get('page', '')
        position = request.form.get('position', '')
        link_url = request.form.get('link_url', '').strip()
        sort_order = request.form.get('sort_order', type=int) or 0
        image = request.files.get('image')

        page_keys = [key for key, _ in BANNER_PAGE_CHOICES]
        position_keys = [key for key, _ in BANNER_POSITION_CHOICES]

        if not title or page not in page_keys or position not in position_keys:
            flash('Заполните название и выберите страницу/место.', 'error')
            return render_template(
                'admin/banner_form.html', active='banners', banner=banner,
                page_choices=BANNER_PAGE_CHOICES, position_choices=BANNER_POSITION_CHOICES,
            )

        if image and image.filename and not allowed_image(image.filename):
            flash('Допустимые форматы изображения: JPG, PNG, WEBP.', 'error')
            return render_template(
                'admin/banner_form.html', active='banners', banner=banner,
                page_choices=BANNER_PAGE_CHOICES, position_choices=BANNER_POSITION_CHOICES,
            )

        banner.title = title
        banner.page = page
        banner.position = position
        banner.link_url = link_url or None
        banner.sort_order = sort_order
        if image and image.filename:
            old_file_path = os.path.join(current_app.root_path, 'static', banner.image_path)
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
            banner.image_path = save_upload(image)
        db.session.commit()
        flash('Баннер обновлён.', 'success')
        return redirect(url_for('admin.banners_list'))

    return render_template(
        'admin/banner_form.html', active='banners', banner=banner,
        page_choices=BANNER_PAGE_CHOICES, position_choices=BANNER_POSITION_CHOICES,
    )


@bp.route('/banners/<int:banner_id>/delete', methods=['POST'])
@section_required('banners')
@roles_required('admin', 'editor')
def banners_delete(banner_id):
    banner = Banner.query.get_or_404(banner_id)
    file_path = os.path.join(current_app.root_path, 'static', banner.image_path)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.session.delete(banner)
    db.session.commit()
    flash('Баннер удалён.', 'success')
    return redirect(url_for('admin.banners_list'))


# ---------- Логотипы партнёров (полоса перед подвалом) ----------

@bp.route('/partners')
@section_required('partners')
def partners_list():
    logos = PartnerLogo.query.order_by(PartnerLogo.sort_order).all()
    return render_template('admin/partners_list.html', active='partners', logos=logos)


@bp.route('/partners/new', methods=['GET', 'POST'])
@section_required('partners')
@roles_required('admin', 'editor')
def partners_new():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        link_url = request.form.get('link_url', '').strip()
        sort_order = request.form.get('sort_order', type=int) or 0
        image = request.files.get('image')

        if not name:
            flash('Название партнёра обязательно.', 'error')
            return render_template('admin/partner_form.html', active='partners', logo=None)

        if not image or not image.filename:
            flash('Изображение логотипа обязательно.', 'error')
            return render_template('admin/partner_form.html', active='partners', logo=None)

        if not allowed_image(image.filename):
            flash('Допустимые форматы изображения: JPG, PNG, WEBP.', 'error')
            return render_template('admin/partner_form.html', active='partners', logo=None)

        logo = PartnerLogo(
            name=name,
            link_url=link_url or None,
            sort_order=sort_order,
            is_active=bool(request.form.get('is_active')),
            image_path=save_upload(image),
        )
        db.session.add(logo)
        db.session.commit()
        flash('Логотип добавлен.', 'success')
        return redirect(url_for('admin.partners_list'))

    return render_template('admin/partner_form.html', active='partners', logo=None)


@bp.route('/partners/<int:logo_id>/edit', methods=['GET', 'POST'])
@section_required('partners')
@roles_required('admin', 'editor')
def partners_edit(logo_id):
    logo = PartnerLogo.query.get_or_404(logo_id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        link_url = request.form.get('link_url', '').strip()
        sort_order = request.form.get('sort_order', type=int) or 0
        image = request.files.get('image')

        if not name:
            flash('Название партнёра обязательно.', 'error')
            return render_template('admin/partner_form.html', active='partners', logo=logo)

        if image and image.filename and not allowed_image(image.filename):
            flash('Допустимые форматы изображения: JPG, PNG, WEBP.', 'error')
            return render_template('admin/partner_form.html', active='partners', logo=logo)

        logo.name = name
        logo.link_url = link_url or None
        logo.sort_order = sort_order
        logo.is_active = bool(request.form.get('is_active'))
        if image and image.filename:
            old_file_path = os.path.join(current_app.root_path, 'static', logo.image_path)
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
            logo.image_path = save_upload(image)
        db.session.commit()
        flash('Логотип обновлён.', 'success')
        return redirect(url_for('admin.partners_list'))

    return render_template('admin/partner_form.html', active='partners', logo=logo)


@bp.route('/partners/<int:logo_id>/delete', methods=['POST'])
@section_required('partners')
@roles_required('admin', 'editor')
def partners_delete(logo_id):
    logo = PartnerLogo.query.get_or_404(logo_id)
    file_path = os.path.join(current_app.root_path, 'static', logo.image_path)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.session.delete(logo)
    db.session.commit()
    flash('Логотип удалён.', 'success')
    return redirect(url_for('admin.partners_list'))


# ---------- Медиа (альбомы и видео) ----------

@bp.route('/media')
@section_required('media')
def media_list():
    albums = MediaAlbum.query.order_by(MediaAlbum.published_at.desc()).all()
    videos = MediaVideo.query.order_by(MediaVideo.published_at.desc()).all()
    return render_template('admin/media_list.html', active='media', albums=albums, videos=videos)


@bp.route('/media/albums/new', methods=['GET', 'POST'])
@section_required('media')
@roles_required('admin', 'editor')
def media_album_new():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        photos_count = request.form.get('photos_count', type=int) or 1
        cover = request.files.get('cover')
        gallery_files = [f for f in request.files.getlist('photos') if f and f.filename]

        if not title:
            flash('Название альбома обязательно.', 'error')
            return render_template('admin/media_album_form.html', active='media', album=None)

        if not cover or not cover.filename:
            flash('Обложка альбома обязательна.', 'error')
            return render_template('admin/media_album_form.html', active='media', album=None)

        bad_images = [f for f in [cover, *gallery_files] if f and f.filename and not allowed_image(f.filename)]
        if bad_images:
            flash('Допустимые форматы изображения: JPG, PNG, WEBP.', 'error')
            return render_template('admin/media_album_form.html', active='media', album=None)

        album = MediaAlbum(
            title=title,
            photos_count=photos_count,
            is_published=bool(request.form.get('is_published')),
            cover_path=save_upload(cover),
        )
        db.session.add(album)
        for gallery_file in gallery_files:
            db.session.add(MediaAlbumPhoto(album=album, file_path=save_upload(gallery_file)))
        db.session.commit()
        flash('Альбом добавлен.', 'success')
        return redirect(url_for('admin.media_list'))

    return render_template('admin/media_album_form.html', active='media', album=None)


@bp.route('/media/albums/<int:album_id>/edit', methods=['GET', 'POST'])
@section_required('media')
@roles_required('admin', 'editor')
def media_album_edit(album_id):
    album = MediaAlbum.query.get_or_404(album_id)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        photos_count = request.form.get('photos_count', type=int) or 1
        cover = request.files.get('cover')
        gallery_files = [f for f in request.files.getlist('photos') if f and f.filename]

        if not title:
            flash('Название альбома обязательно.', 'error')
            return render_template('admin/media_album_form.html', active='media', album=album)

        bad_images = [f for f in [cover, *gallery_files] if f and f.filename and not allowed_image(f.filename)]
        if bad_images:
            flash('Допустимые форматы изображения: JPG, PNG, WEBP.', 'error')
            return render_template('admin/media_album_form.html', active='media', album=album)

        album.title = title
        album.photos_count = photos_count
        album.is_published = bool(request.form.get('is_published'))
        if cover and cover.filename:
            old_file_path = os.path.join(current_app.root_path, 'static', album.cover_path)
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
            album.cover_path = save_upload(cover)
        for gallery_file in gallery_files:
            db.session.add(MediaAlbumPhoto(album=album, file_path=save_upload(gallery_file)))
        db.session.commit()
        flash('Альбом обновлён.', 'success')
        return redirect(url_for('admin.media_list'))

    return render_template('admin/media_album_form.html', active='media', album=album)


@bp.route('/media/albums/<int:album_id>/photos/<int:photo_id>/delete', methods=['POST'])
@section_required('media')
@roles_required('admin', 'editor')
def media_album_photo_delete(album_id, photo_id):
    photo = MediaAlbumPhoto.query.filter_by(id=photo_id, album_id=album_id).first_or_404()
    file_path = os.path.join(current_app.root_path, 'static', photo.file_path)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.session.delete(photo)
    db.session.commit()
    flash('Фото удалено.', 'success')
    return redirect(url_for('admin.media_album_edit', album_id=album_id))


@bp.route('/media/albums/<int:album_id>/delete', methods=['POST'])
@section_required('media')
@roles_required('admin', 'editor')
def media_album_delete(album_id):
    album = MediaAlbum.query.get_or_404(album_id)
    file_path = os.path.join(current_app.root_path, 'static', album.cover_path)
    if os.path.exists(file_path):
        os.remove(file_path)
    for photo in album.photos:
        photo_path = os.path.join(current_app.root_path, 'static', photo.file_path)
        if os.path.exists(photo_path):
            os.remove(photo_path)
    db.session.delete(album)
    db.session.commit()
    flash('Альбом удалён.', 'success')
    return redirect(url_for('admin.media_list'))


@bp.route('/media/videos/new', methods=['GET', 'POST'])
@section_required('media')
@roles_required('admin', 'editor')
def media_video_new():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        video_url = request.form.get('video_url', '').strip()
        thumbnail = request.files.get('thumbnail')
        use_youtube_thumbnail = bool(request.form.get('use_youtube_thumbnail'))

        if not title:
            flash('Название видео обязательно.', 'error')
            return render_template('admin/media_video_form.html', active='media', video=None)

        if use_youtube_thumbnail:
            youtube_id = extract_youtube_id(video_url)
            if not youtube_id:
                flash('Не удалось определить обложку YouTube — проверьте ссылку на видео.', 'error')
                return render_template('admin/media_video_form.html', active='media', video=None)
            thumbnail_path = youtube_thumbnail_url(youtube_id)
        else:
            if not thumbnail or not thumbnail.filename:
                flash('Превью видео обязательно (или включите обложку с YouTube).', 'error')
                return render_template('admin/media_video_form.html', active='media', video=None)
            if not allowed_image(thumbnail.filename):
                flash('Допустимые форматы изображения: JPG, PNG, WEBP.', 'error')
                return render_template('admin/media_video_form.html', active='media', video=None)
            thumbnail_path = save_upload(thumbnail)

        video = MediaVideo(
            title=title,
            video_url=video_url or None,
            is_published=bool(request.form.get('is_published')),
            thumbnail_path=thumbnail_path,
        )
        db.session.add(video)
        db.session.commit()
        flash('Видео добавлено.', 'success')
        return redirect(url_for('admin.media_list'))

    return render_template('admin/media_video_form.html', active='media', video=None)


@bp.route('/media/videos/<int:video_id>/edit', methods=['GET', 'POST'])
@section_required('media')
@roles_required('admin', 'editor')
def media_video_edit(video_id):
    video = MediaVideo.query.get_or_404(video_id)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        video_url = request.form.get('video_url', '').strip()
        thumbnail = request.files.get('thumbnail')
        use_youtube_thumbnail = bool(request.form.get('use_youtube_thumbnail'))

        if not title:
            flash('Название видео обязательно.', 'error')
            return render_template('admin/media_video_form.html', active='media', video=video)

        if not use_youtube_thumbnail and thumbnail and thumbnail.filename and not allowed_image(thumbnail.filename):
            flash('Допустимые форматы изображения: JPG, PNG, WEBP.', 'error')
            return render_template('admin/media_video_form.html', active='media', video=video)

        def delete_old_local_thumbnail():
            if video.thumbnail_path and not video.thumbnail_path.startswith('http'):
                old_file_path = os.path.join(current_app.root_path, 'static', video.thumbnail_path)
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)

        video.title = title
        video.video_url = video_url or None
        video.is_published = bool(request.form.get('is_published'))

        if use_youtube_thumbnail:
            youtube_id = extract_youtube_id(video_url)
            if not youtube_id:
                flash('Не удалось определить обложку YouTube — проверьте ссылку на видео.', 'error')
                return render_template('admin/media_video_form.html', active='media', video=video)
            delete_old_local_thumbnail()
            video.thumbnail_path = youtube_thumbnail_url(youtube_id)
        elif thumbnail and thumbnail.filename:
            delete_old_local_thumbnail()
            video.thumbnail_path = save_upload(thumbnail)

        db.session.commit()
        flash('Видео обновлено.', 'success')
        return redirect(url_for('admin.media_list'))

    return render_template('admin/media_video_form.html', active='media', video=video)


@bp.route('/media/videos/<int:video_id>/delete', methods=['POST'])
@section_required('media')
@roles_required('admin', 'editor')
def media_video_delete(video_id):
    video = MediaVideo.query.get_or_404(video_id)
    if video.thumbnail_path and not video.thumbnail_path.startswith('http'):
        file_path = os.path.join(current_app.root_path, 'static', video.thumbnail_path)
        if os.path.exists(file_path):
            os.remove(file_path)
    db.session.delete(video)
    db.session.commit()
    flash('Видео удалено.', 'success')
    return redirect(url_for('admin.media_list'))


# ---------- Пользователи (только admin) ----------

def _sections_from_form():
    return ','.join(key for key in request.form.getlist('sections') if key in SECTION_KEYS)


@bp.route('/users')
@roles_required('admin')
def users_list():
    users = User.query.order_by(User.username).all()
    return render_template(
        'admin/users_list.html', active='users', users=users,
        role_choices=ROLE_CHOICES, section_choices=SECTION_CHOICES,
    )


@bp.route('/users/new', methods=['GET', 'POST'])
@roles_required('admin')
def users_new():
    regions = RegionalFederation.query.order_by(RegionalFederation.name).all()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'viewer')

        if not username or not password:
            flash('Логин и пароль обязательны.', 'error')
            return render_template(
                'admin/user_form.html', active='users', user=None,
                role_choices=ROLE_CHOICES, section_choices=SECTION_CHOICES, regions=regions,
            )

        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким логином уже существует.', 'error')
            return render_template(
                'admin/user_form.html', active='users', user=None,
                role_choices=ROLE_CHOICES, section_choices=SECTION_CHOICES, regions=regions,
            )

        if role not in ROLE_CHOICES:
            role = 'viewer'

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
            region=request.form.get('region', '').strip() or None if role == 'region_rep' else None,
            is_active=True,
            allowed_sections=_sections_from_form(),
        )
        db.session.add(user)
        db.session.commit()
        flash('Пользователь создан.', 'success')
        return redirect(url_for('admin.users_list'))

    return render_template(
        'admin/user_form.html', active='users', user=None,
        role_choices=ROLE_CHOICES, section_choices=SECTION_CHOICES, regions=regions,
    )


@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@roles_required('admin')
def users_edit(user_id):
    user = User.query.get_or_404(user_id)
    regions = RegionalFederation.query.order_by(RegionalFederation.name).all()

    if request.method == 'POST':
        role = request.form.get('role', user.role)
        is_active = bool(request.form.get('is_active'))

        if role not in ROLE_CHOICES:
            flash('Недопустимая роль.', 'error')
            return render_template(
                'admin/user_form.html', active='users', user=user,
                role_choices=ROLE_CHOICES, section_choices=SECTION_CHOICES, regions=regions,
            )

        if is_last_active_admin(user) and (role != 'admin' or not is_active):
            flash(
                'Нельзя понизить в роли или отключить последнего активного администратора.',
                'error',
            )
            return render_template(
                'admin/user_form.html', active='users', user=user,
                role_choices=ROLE_CHOICES, section_choices=SECTION_CHOICES, regions=regions,
            )

        user.role = role
        user.region = request.form.get('region', '').strip() or None if role == 'region_rep' else None
        user.is_active = is_active
        user.allowed_sections = _sections_from_form()

        new_password = request.form.get('password', '')
        if new_password:
            user.password_hash = generate_password_hash(new_password)

        db.session.commit()
        flash('Доступ пользователя обновлён.', 'success')
        return redirect(url_for('admin.users_list'))

    return render_template(
        'admin/user_form.html', active='users', user=user,
        role_choices=ROLE_CHOICES, section_choices=SECTION_CHOICES, regions=regions,
    )


# ---------- Статус синхронизации ----------

@bp.route('/sync')
@section_required('sync')
def sync_status():
    return render_template('admin/sync_status.html', active='sync', latest_syncs=latest_sync_by_source())


# ---------- Заявки на семинары (отправка в SPORTS_REFEREE) ----------

@bp.route('/seminar-applications')
@roles_required('admin')
def seminar_applications_list():
    applications = (
        SeminarApplicationSubmission.query
        .join(Event)
        .order_by(SeminarApplicationSubmission.created_at.desc())
        .all()
    )
    return render_template(
        'admin/seminar_applications_list.html', active='seminar_applications',
        applications=applications,
    )


@bp.route('/seminar-applications/<int:submission_id>/send', methods=['POST'])
@roles_required('admin')
def seminar_application_send(submission_id):
    submission = SeminarApplicationSubmission.query.get_or_404(submission_id)
    event = submission.event

    if not event.source_id:
        flash('Мероприятие не синхронизировано с SPORTS_REFEREE — отправить нельзя.', 'error')
        return redirect(url_for('admin.seminar_applications_list'))

    if submission.referee_application_id:
        success, message = обновить_заявку(submission, event.source_id, submission.referee_application_id)
    else:
        success, message, referee_application_id = отправить_заявку(submission, event.source_id)
        if success:
            submission.referee_application_id = referee_application_id

    submission.send_status = 'sent' if success else 'failed'
    submission.send_message = message
    db.session.commit()

    flash(message, 'success' if success else 'danger')
    return redirect(url_for('admin.seminar_applications_list'))


# ---------- Заявки на регистрацию федераций ----------

@bp.route('/federation-requests')
@roles_required('admin')
def federation_requests_list():
    requests_ = (
        FederationRegistrationRequest.query
        .order_by(FederationRegistrationRequest.created_at.desc())
        .all()
    )
    return render_template(
        'admin/federation_requests_list.html', active='federation_requests', requests=requests_,
    )


@bp.route('/federation-requests/<int:request_id>/approve', methods=['POST'])
@roles_required('admin')
def federation_request_approve(request_id):
    req = FederationRegistrationRequest.query.get_or_404(request_id)
    if req.status != 'pending':
        flash('Заявка уже обработана.', 'error')
        return redirect(url_for('admin.federation_requests_list'))

    if User.query.filter_by(username=req.email).first():
        flash('Пользователь с таким email уже существует — заявка не может быть одобрена повторно.', 'error')
        return redirect(url_for('admin.federation_requests_list'))

    user = User(
        username=req.email,
        password_hash=req.password_hash,
        role='region_rep',
        region=req.full_name,
        is_active=True,
    )
    db.session.add(user)
    req.status = 'approved'
    req.reviewed_at = datetime.utcnow()
    db.session.commit()

    flash(f'Заявка одобрена, создан вход для {req.email}.', 'success')
    return redirect(url_for('admin.federation_requests_list'))


@bp.route('/federation-requests/<int:request_id>/reject', methods=['POST'])
@roles_required('admin')
def federation_request_reject(request_id):
    req = FederationRegistrationRequest.query.get_or_404(request_id)
    if req.status != 'pending':
        flash('Заявка уже обработана.', 'error')
        return redirect(url_for('admin.federation_requests_list'))

    req.status = 'rejected'
    req.reviewed_at = datetime.utcnow()
    db.session.commit()

    flash('Заявка отклонена.', 'success')
    return redirect(url_for('admin.federation_requests_list'))


# ---------- Заявки на сброс пароля ----------

@bp.route('/password-reset-requests')
@roles_required('admin')
def password_reset_requests_list():
    requests_ = (
        PasswordResetRequest.query
        .order_by(PasswordResetRequest.created_at.desc())
        .all()
    )
    return render_template(
        'admin/password_reset_requests_list.html', active='password_reset_requests', requests=requests_,
    )


@bp.route('/password-reset-requests/<int:request_id>/resolve', methods=['POST'])
@roles_required('admin')
def password_reset_request_resolve(request_id):
    req = PasswordResetRequest.query.get_or_404(request_id)
    req.status = 'resolved'
    req.resolved_at = datetime.utcnow()
    db.session.commit()
    flash('Заявка отмечена как обработанная.', 'success')
    return redirect(url_for('admin.password_reset_requests_list'))
