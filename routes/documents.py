"""Нормативные документы, разбитые по категориям."""
from flask import Blueprint, render_template

from models import Document

bp = Blueprint('documents', __name__)


@bp.route('/')
def index():
    documents = Document.query.order_by(Document.doc_category, Document.title).all()

    documents_by_category = {}
    for document in documents:
        documents_by_category.setdefault(document.doc_category or 'Прочее', []).append(document)

    return render_template('documents/list.html', documents_by_category=documents_by_category)
