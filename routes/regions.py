"""Региональные федерации субъектов ЦФО."""
from flask import Blueprint, render_template

from models import RegionalFederation

bp = Blueprint('regions', __name__)


@bp.route('/')
def index():
    regional_federations = RegionalFederation.query.order_by(RegionalFederation.name).all()
    return render_template(
        'regions/list.html',
        regional_federations=regional_federations,
        breadcrumbs=[{'label': 'Региональные федерации'}],
    )
