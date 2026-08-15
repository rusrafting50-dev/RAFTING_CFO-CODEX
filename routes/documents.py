"""Рафтинг ЦФО: нормативные документы, разбитые по категориям и разделам."""
from flask import Blueprint, render_template, request

from models import Document, DocumentCategory, DocumentSection

bp = Blueprint('documents', __name__)


@bp.route('/')
def index():
    categories = DocumentCategory.query.order_by(DocumentCategory.name).all()

    selected_section_id = request.args.get('section', type=int)
    selected_section = DocumentSection.query.get(selected_section_id) if selected_section_id else None

    if selected_section:
        documents = (
            Document.query.filter_by(section_id=selected_section.id)
            .order_by(Document.uploaded_at.desc(), Document.title)
            .all()
        )
    else:
        documents = Document.query.order_by(Document.uploaded_at.desc(), Document.title).all()

    return render_template(
        'documents/list.html', documents=documents, categories=categories,
        selected_section=selected_section,
    )
