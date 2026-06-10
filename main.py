from http import HTTPStatus
from flask import abort
from flask_login import LoginManager, login_required, login_user, logout_user, current_user, login_manager
from app.models.domain import db
from flask import Flask, render_template, make_response, redirect, request, session, g, flash, url_for, Blueprint, jsonify
from flask_cors import CORS, cross_origin
from folium import Element
from datetime import timedelta, datetime
from sqlalchemy.sql import func
import requests
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
import os
from werkzeug.utils import secure_filename
import gpxpy
import pandas as pd
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry, WKTElement
from shapely.geometry import LineString
from app.models.domain import Base, User, Collection, GPXTrack, TravelWish
import app.models .persistence as persistence
import geopandas as gpd
# from sqlalchemy import select, func
from app.utils.gpxutils import calculate_elevation_gain
from flask_sqlalchemy import SQLAlchemy
import geocoder
import traceback
from sqlalchemy.orm import joinedload
from flask_login import LoginManager, login_required


ALLOWED_EXTENSIONS = {'gpx', 'tcx', 'fit', 'csv'}
load_dotenv()  # Charger les variables d'environnement à partir du fichier .env


login_manager = LoginManager()


def create_app():

    app = Flask(__name__, static_url_path='',
                static_folder='static')
    login_manager.init_app(app)

    CORS(app)
    import app.models as models
    import app.routes as routes

    models.init_app(app)
    routes.init_app(app)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)
    app.secret_key = "123"
    app.config["SQLALCHEMY_DATABASE_URI"] = f'postgresql+psycopg://{os.environ["AIVEN_USERNAME"]}:{os.environ["AIVEN_PASSWORD"]}@{os.environ["AIVEN_HOST"]}:{os.environ["AIVEN_PORT"]}/{os.environ["AIVEN_DBNAME"]}?sslmode=require'
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 2,
        'max_overflow': 20,
        'pool_timeout': 30
    }
    from app.routes import auth
    from app.routes import explore
    from app.routes import api

    app.register_blueprint(auth.bp)
    app.register_blueprint(explore.bp)
    app.register_blueprint(api.bp)
    db.init_app(app)

    return app


app = create_app()
with app.app_context():
    db.create_all()
print("app created")


@login_manager.user_loader
def load_user(id):
    # 1. Fetch against the database a user by `id`
    # 2. Create a new object of `User` class and return it.
    # u = DBUsers.query.get(id)
    return db.session.query(User).filter_by(uuid=id).first()


@login_manager.unauthorized_handler
def unauthorized():
    if request.blueprint == 'api':
        abort(HTTPStatus.UNAUTHORIZED)
    return redirect(url_for('site.login'))


@app.route("/")
def index():
    return redirect("/explore")


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['POST'])
def upload_file():
    print("uploading file...")
    owner = session['user']['sub']
    engine = persistence.get_engine()
    # check if the post request has the file part
    if 'file' not in request.files:
        # flash('No file part')
        return jsonify({'message': 'File uploaded unsuccessfully : no file part'})
    file = request.files['file']
    comment = request.form.get('comment')
    type = request.form.get('activity_type')
    print("type : " + type)
    # If the user does not select a file, the browser submits an
    # empty file without a filename.
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        Session = sessionmaker(bind=engine)
        sess = Session()
        gpx = gpxpy.parse(file)
        for track in gpx.tracks:
            print(track.name)
            start_time, end_time = gpx.get_time_bounds()
            link = gpx.link
            # Calculate 3D distance in meters
            distance_3d = track.length_3d()
            print(f"Track: {track.name}, Distance: {distance_3d:.2f} meters")

            # Calculate 2D distance
            distance_2d = track.length_2d()
            print(
                f"Track: {track.name}, 2D Distance: {distance_2d:.2f} meters")
            # elevation gain
            elevation_gain, elevation_loss = calculate_elevation_gain(gpx)
            print(
                f"Track: {track.name}, Elevation Gain: {elevation_gain:.2f} meters")
            # Access the first point of the first track
            start_point = None
            if track.segments:
                first_segment = track.segments[0]
                if first_segment.points:
                    start_point = first_segment.points[0]
                    print(f"Start Latitude: {start_point.latitude}")
                    print(f"Start Longitude: {start_point.longitude}")
                    print(f"Start Elevation: {start_point.elevation}")
                    for segment in track.segments:
                        point = segment.points[0]
                        print(
                            'Start at ({0},{1}) -> {2}'.format(point.latitude, point.longitude, point.elevation))

            g = geocoder.google([start_point.latitude, start_point.longitude],
                                method='reverse', key=os.getenv('GOOGLE_API_KEY'))
            print(g.json)
            # print( g.country_long +">" + g.state_long + ">" + g.county + ">" + g.city)
            start_point_geo = {'country': g.country_long,
                               'state': g.state_long, 'county': g.county, 'city': g.city}

            points = [(point.longitude, point.latitude, point.elevation)
                      for segment in track.segments for point in segment.points]
            line_string = LineString(points)

            # Convert to WKT for insertion
            wkt = line_string.wkt
            print("start time " + str(start_time))
            try:
                new_track = GPXTrack(name=track.name, geom=WKTElement(wkt, srid=4326), owner=owner, type=type, elevation_gain=elevation_gain, elevation_loss=elevation_loss,
                                     link=link, start_time=start_time, end_time=end_time, insert_date=datetime.now().isoformat(timespec='seconds'), length=track.length_3d(), comment=comment, start_point_geo=start_point_geo)
                sess.add(new_track)
                print(
                    f"Inserted track: {track.name} with {len(points)} points.")
                sess.commit()
                sess.close()
            except Exception as e:
                print(f"Error inserting track: {track.name}, Error: {e}")
                sess.rollback()
                sess.close()
        for waypoint in gpx.waypoints:
            print('waypoint {0} -> ({1},{2})'.format(waypoint.name,
                  waypoint.latitude, waypoint.longitude))

        for route in gpx.routes:
            print('Route:')
        print("upload ok")
        # return redirect("/maplibre")
        return jsonify({'bounds': [[gpx.get_bounds().min_longitude, gpx.get_bounds().min_latitude], [gpx.get_bounds().max_longitude, gpx.get_bounds().max_latitude]], 'message': 'File uploaded successfully !'})


@app.route('/search_places', methods=['GET'])
@login_required
def search_places():
    api_key = os.getenv('GOOGLE_API_KEY')
    # Retrieve the search term sent by jQuery
    search = request.args.get('search')
    print("search : " + search)
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": search,
        "key": api_key,
        "language": "fr"  # Optionnel : spécifie la langue des résultats
    }

    response = requests.get(url, params=params)
    data = response.json()
    # print(data)
    # Return JSON response
    return jsonify(results=data["results"])


@app.route('/collection/<int:collection_id>')
def view_collection(collection_id):
    if 'user' not in session:
        return redirect(url_for('auth.login'))

    db_session = db.session
    current_user = db.session.query(User).filter_by(
        uuid=session['user'].get('sub')).first()
    if not current_user:
        return redirect(url_for('auth.login'))

    db_session.close()
    return render_template('collection.html')


@app.route('/mapbox')
def mapbox():
    return render_template('mapbox.html')


@app.route('/explore')
def maplibre():
    return render_template('maplibre.html')


@app.route('/track/<int:track_id>')
def track_detail(track_id):
    # Render a detail page for a track. JS will fetch track data and waypoints.
    current_user_sub = None
    if 'user' in session:
        current_user_sub = session['user'].get('sub')

    # Try to fetch minimal ownership info to show edit form when appropriate
    track = db.session.query(GPXTrack).filter_by(id=track_id).first()
    is_owner = False
    if track and current_user_sub and track.owner == current_user_sub:
        is_owner = True

    return render_template('detail.html', track_id=track_id, is_owner=is_owner)


@app.route('/cesiumjs')
def cesiumjs():
    return render_template('cesiumjs.html')

# ======================== TRAVEL WISHES ROUTES ========================


@app.route('/travel-wishes')
def travel_wishes():
    if 'user' not in session:
        return redirect(url_for('auth.login'))

    current_user = db.session.query(User).filter_by(
        uuid=session['user'].get('sub')).first()
    if not current_user:
        return redirect(url_for('auth.login'))

    wishes = db.session.query(TravelWish).filter_by(
        user_id=current_user.id).all()
    return render_template('travel_wishes.html', wishes=wishes)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
