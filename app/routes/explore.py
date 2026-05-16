from flask import (
    Blueprint, request, g, redirect, url_for, flash, render_template, session
)
import os
import requests
from oauthlib import oauth2
import json
from app.models.domain import db
from app.models.domain import User, Collection
bp = Blueprint('explore', __name__, url_prefix='/explore')


@bp.route('/map')
def explore():
    db_session = db.session
    with db_session.connection() as conn:
        user_collections = []
        if 'user' in session:
            current_user = db.session.query(User).filter_by(
                uuid=session['user'].get('sub')).first()
            if current_user:
                user_collections = current_user.collections

    db_session.close()

    return render_template(
        'map.html', user_collections=user_collections)
