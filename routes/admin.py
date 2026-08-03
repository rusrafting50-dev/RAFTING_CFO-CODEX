"""Панель администратора: вход, дашборд, управление контентом."""
import os
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
    Athlete, Competition, CompetitionDocument, Document, FederationMember,
    News, Referee, SyncLog, User, db,
)

bp = Blueprint('admin', __name__)

ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'docx'}
SYNC_SOURCES = ['COREZ', 'REGTEAM_RAFTING', 'SPORTS_REFEREE']

BODY_CHOICES = ['исполком', 'коллегия_судей', 'тренерский_совет', 'комитет_представителей']
DOC_CATEGORY_CHOICES = ['федеральный', 'региональный', 'wrf', 'фрр', 'федерация']
NEWS_CATEGORY_CHOICES = ['соревнование', 'мероприятие', 'федерация']
NEWS_LEVEL_CHOICES = ['цфо', 'регион', 'отделение', 'клуб']
ROLE_CHOICES = ['admin', 'editor', 'viewer']
# Разделы панели, доступ к которым назначается сотруднику индивидуально
# (роль admin получает их все автоматически, см. User.can_access).
SECTION_CHOICES = [
    ('news', 'Новости'),
    ('competitions', 'Соревнования'),
    ('documents', 'Документы'),
    ('members', 'Члены органов'),
    ('sync', 'Синхронизация'),
]
SECTION_KEYS = [key for key, _ in SECTION_CHOICES]
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

        if not title or not content:
            flash('Заголовок и текст новости обязательны.', 'error')
            return render_template(
                'admin/news_form.html', active='news', news=None,
                category_choices=NEWS_CATEGORY_CHOICES, level_choices=NEWS_LEVEL_CHOICES,
            )

        news_item = News(
            title=title,
            content=content,
            category=request.form.get('category') or None,
            level=request.form.get('level') or None,
            is_published=bool(request.form.get('is_published')),
            created_by=current_user.id,
        )
        db.session.add(news_item)
        db.session.commit()
        flash('Новость создана.', 'success')
        return redirect(url_for('admin.news_list'))

    return render_template(
        'admin/news_form.html', active='news', news=None,
        category_choices=NEWS_CATEGORY_CHOICES, level_choices=NEWS_LEVEL_CHOICES,
    )


@bp.route('/news/<int:news_id>/edit', methods=['GET', 'POST'])
@section_required('news')
@roles_required('admin', 'editor')
def news_edit(news_id):
    news_item = News.query.get_or_404(news_id)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()

        if not title or not content:
            flash('Заголовок и текст новости обязательны.', 'error')
            return render_template(
                'admin/news_form.html', active='news', news=news_item,
                category_choices=NEWS_CATEGORY_CHOICES, level_choices=NEWS_LEVEL_CHOICES,
            )

        news_item.title = title
        news_item.content = content
        news_item.category = request.form.get('category') or None
        news_item.level = request.form.get('level') or None
        news_item.is_published = bool(request.form.get('is_published'))
        db.session.commit()
        flash('Новость обновлена.', 'success')
        return redirect(url_for('admin.news_list'))

    return render_template(
        'admin/news_form.html', active='news', news=news_item,
        category_choices=NEWS_CATEGORY_CHOICES, level_choices=NEWS_LEVEL_CHOICES,
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


@bp.route('/news/<int:news_id>/toggle-publish', methods=['POST'])
@section_required('news')
@roles_required('admin', 'editor')
def news_toggle_publish(news_id):
    news_item = News.query.get_or_404(news_id)
    news_item.is_published = not news_item.is_published
    db.session.commit()
    flash('Публикация новости обновлена.', 'success')
    return redirect(url_for('admin.news_list'))


# ---------- Документы ----------

@bp.route('/documents')
@section_required('documents')
def documents_list():
    items = Document.query.order_by(Document.doc_category, Document.title).all()
    return render_template('admin/documents_list.html', active='documents', documents=items)


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
                'admin/document_form.html', active='documents', category_choices=DOC_CATEGORY_CHOICES,
            )

        if not allowed_document(file.filename):
            flash('Допустимые форматы файлов: PDF, DOCX.', 'error')
            return render_template(
                'admin/document_form.html', active='documents', category_choices=DOC_CATEGORY_CHOICES,
            )

        filename = secure_filename(file.filename)
        unique_name = f"{datetime.utcnow():%Y%m%d%H%M%S}_{filename}"
        upload_dir = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, unique_name))

        document = Document(
            title=title,
            doc_category=request.form.get('doc_category') or None,
            level=request.form.get('level') or None,
            file_path=f"uploads/{unique_name}",
        )
        db.session.add(document)
        db.session.commit()
        flash('Документ загружен.', 'success')
        return redirect(url_for('admin.documents_list'))

    return render_template(
        'admin/document_form.html', active='documents', category_choices=DOC_CATEGORY_CHOICES,
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
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'viewer')

        if not username or not password:
            flash('Логин и пароль обязательны.', 'error')
            return render_template(
                'admin/user_form.html', active='users', user=None,
                role_choices=ROLE_CHOICES, section_choices=SECTION_CHOICES,
            )

        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким логином уже существует.', 'error')
            return render_template(
                'admin/user_form.html', active='users', user=None,
                role_choices=ROLE_CHOICES, section_choices=SECTION_CHOICES,
            )

        if role not in ROLE_CHOICES:
            role = 'viewer'

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
            is_active=True,
            allowed_sections=_sections_from_form(),
        )
        db.session.add(user)
        db.session.commit()
        flash('Пользователь создан.', 'success')
        return redirect(url_for('admin.users_list'))

    return render_template(
        'admin/user_form.html', active='users', user=None,
        role_choices=ROLE_CHOICES, section_choices=SECTION_CHOICES,
    )


@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@roles_required('admin')
def users_edit(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        role = request.form.get('role', user.role)
        is_active = bool(request.form.get('is_active'))

        if role not in ROLE_CHOICES:
            flash('Недопустимая роль.', 'error')
            return render_template(
                'admin/user_form.html', active='users', user=user,
                role_choices=ROLE_CHOICES, section_choices=SECTION_CHOICES,
            )

        if is_last_active_admin(user) and (role != 'admin' or not is_active):
            flash(
                'Нельзя понизить в роли или отключить последнего активного администратора.',
                'error',
            )
            return render_template(
                'admin/user_form.html', active='users', user=user,
                role_choices=ROLE_CHOICES, section_choices=SECTION_CHOICES,
            )

        user.role = role
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
        role_choices=ROLE_CHOICES, section_choices=SECTION_CHOICES,
    )


# ---------- Статус синхронизации ----------

@bp.route('/sync')
@section_required('sync')
def sync_status():
    return render_template('admin/sync_status.html', active='sync', latest_syncs=latest_sync_by_source())
