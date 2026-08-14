"""Рафтинг ЦФО: нормативные документы, разбитые по категориям."""
from flask import Blueprint, render_template, request

from models import Document, DocumentCategory

bp = Blueprint('documents', __name__)


@bp.route('/')
def index():
    categories = DocumentCategory.query.order_by(DocumentCategory.name).all()
    selected_category = request.args.get('category', '')

    documents_by_category = {
        category.name: (
            Document.query.filter_by(doc_category=category.name)
            .order_by(Document.uploaded_at.desc(), Document.title)
            .all()
        )
        for category in categories
    }

    if selected_category:
        documents = documents_by_category.get(selected_category, [])
    else:
        documents = Document.query.order_by(Document.uploaded_at.desc(), Document.title).all()

    return render_template(
        'documents/list.html', documents=documents, categories=categories,
        documents_by_category=documents_by_category, selected_category=selected_category,
    )
