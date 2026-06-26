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
    user_collections = []
    current_user_uuid = None
    if 'user' in session:
        current_user = db.session.query(User).filter_by(
            uuid=session['user'].get('sub')).first()
        if current_user:
            user_collections = current_user.collections
            current_user_uuid = current_user.uuid

    return render_template(
        'map.html', user_collections=user_collections, current_user_uuid=current_user_uuid)
