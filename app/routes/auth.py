from flask import (
    Blueprint, request, g, redirect, url_for, flash, render_template, session
)
import os
import requests
from oauthlib import oauth2
import json
from app.models.domain import db
from app.models.domain import User, Collection
bp = Blueprint('auth', __name__, url_prefix='/auth')
DATA = {
    # this tells the auth server that we are invoking authorization workflow
    'response_type': "code",
    # 'redirect_uri':"https://laughing-umbrella-p75jgv4prf75v9-5000.app.github.dev/alltrail", # redirect URI https://console.developers.google.com/apis/credentials
    'redirect_uri': os.environ['GOOGLE_REDIRECT_URI'],
    # resource we are trying to access through Google API
    'scope': 'https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email openid',
    # client ID from https://console.developers.google.com/apis/credentials
    'client_id': os.environ['GOOGLE_CLIENT_ID'],
    'prompt': 'consent'}  # adds a consent screen

URL_DICT = {
    'google_oauth': 'https://accounts.google.com/o/oauth2/v2/auth',  # Google OAuth URI
    # URI to generate token to access Google API
    'token_gen': 'https://oauth2.googleapis.com/token',
    # URI to get the user info
    'get_user_info': 'https://www.googleapis.com/oauth2/v3/userinfo'
}

# Create a Sign in URI
CLIENT = oauth2.WebApplicationClient(os.environ['GOOGLE_CLIENT_ID'])
REQ_URI = CLIENT.prepare_request_uri(
    uri=URL_DICT['google_oauth'],
    redirect_uri=DATA['redirect_uri'],
    scope=DATA['scope'],
    prompt=DATA['prompt'])


@bp.route('/login')
def login():
    return redirect(REQ_URI)


@bp.route('/logout')
def logout():
    session.pop('user', None)
    # redirect to the newly created Sign-In URI
    return redirect("/alltrail")

# auth.py
# def login_required(view):
#     @functools.wraps(view)
#     def wrapped_view(**kwargs):
#         if session.get('user_id') is None:
#             return redirect(url_for('auth.login'))
#         return view(**kwargs)

#     return wrapped_view


@bp.route('/home')
def home():
    "Redirect after Google login & consent"

    # Get the code after authenticating from the URL
    code = request.args.get('code')

    # Generate URL to generate token
    token_url, headers, body = CLIENT.prepare_token_request(
        URL_DICT['token_gen'],
        authorisation_response=request.url,
        redirect_url=request.base_url,
        code=code)

    # Generate token to access Google API
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(os.environ['GOOGLE_CLIENT_ID'], os.environ['GOOGLE_CLIENT_SECRET']))
    print(token_response.content)

    # Parse the token response
    CLIENT.parse_request_body_response(json.dumps(token_response.json()))

    # Add token to the  Google endpoint to get the user info
    # oauthlib uses the token parsed in the previous step
    uri, headers, body = CLIENT.add_token(URL_DICT['get_user_info'])

    # Get the user info
    response_user_info = requests.get(uri, headers=headers, data=body)
    info = response_user_info.json()
    print(info)
    session['user'] = info
    session.permanent = True
    user = User()
    user.name = info['name']
    user.uuid = info['sub']
    user.email = info['email']
    user_db = db.session.query(User).filter_by(
        name=user.name).first()
    if user_db is None:  # register the user if not already in the database
        db.session.add(user)
        db.session.commit()
    print(session['user'])
    return redirect('/alltrail')


@bp.route('/me')
def me():
    "User profile page"
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    user = db.session.query(User).filter_by(
        name=session['user']['name']).first()

    user_id = user.id
#     print(user.collections)
#     collections = db.session.query(Collection).filter(
#         Collection.user_id == user_id).all()

    return render_template('profile.html',  user=user)
