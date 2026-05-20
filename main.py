from app.models.domain import db
from flask import Flask, render_template, make_response, redirect, request, session, g, flash, url_for, Blueprint, jsonify
from flask_cors import CORS, cross_origin
import folium
from folium import Element
from datetime import timedelta, datetime
import requests
import json
from sqlalchemy.sql import func

from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
import os
from werkzeug.utils import secure_filename
import gpxpy
import pandas as pd
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry, WKTElement
from shapely.geometry import LineString, Point
from app.models.domain import Base, User, Collection, GPXTrack, TravelWish, Waypoint
import app.models .persistence as persistence
import geopandas as gpd
from geoalchemy2.shape import to_shape
# from sqlalchemy import select, func
from app.utils.gpxutils import calculate_elevation_gain
from flask_sqlalchemy import SQLAlchemy
import geocoder
import traceback
from sqlalchemy.orm import joinedload

ALLOWED_EXTENSIONS = {'gpx', 'tcx', 'fit', 'csv'}
load_dotenv()  # Charger les variables d'environnement à partir du fichier .env


def create_app():
    import app.models as models
    import app.routes as routes

    app = Flask(__name__, static_url_path='',
                static_folder='static')
    CORS(app)

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


@app.route("/")
def index():
    # return redirect("/alltrail")
    return render_template("index.html")


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['POST'])
def upload_file():
    owner = session['user']['sub']
    print(request.form)
    engine = persistence.get_engine()
    # check if the post request has the file part
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
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
            print(datetime.now().isoformat(timespec='seconds'))
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

        return redirect("/explore/map")


@app.route('/search', methods=['GET'])
def autocomplete():
    # Retrieve the search term sent by jQuery
    search = request.args.get('term')
    print("search : " + search)
    results = ["titi", "tata", "toto"]

    # Return JSON response
    return jsonify(results=results)


@app.route('/collection2/<int:collection_id>')
def view_collection2(collection_id):
    if 'user' not in session:
        return redirect(url_for('auth.login'))

    db_session = db.session
    current_user = db.session.query(User).filter_by(
        uuid=session['user'].get('sub')).first()
    if not current_user:
        return redirect(url_for('auth.login'))

    db_session.close()
    return render_template('collection2.html')


@app.route('/collection/<int:collection_id>')
def view_collection(collection_id):
    if 'user' not in session:
        return redirect(url_for('auth.login'))

    db_session = db.session
    current_user = db.session.query(User).filter_by(
        uuid=session['user'].get('sub')).first()
    if not current_user:
        return redirect(url_for('auth.login'))

    collection = db.session.query(Collection).options(joinedload(Collection.tracks)).filter_by(
        id=collection_id,
        user_id=current_user.id
    ).first()

    if not collection:
        return "Collection not found", 404

    with db_session.connection() as conn:
        sql = f"SELECT t.* FROM gpx_tracks t JOIN collection_track ct ON ct.track_id = t.id WHERE ct.collection_id = {collection_id}"
        gdf_tracks = gpd.GeoDataFrame.from_postgis(
            sql, con=conn, geom_col='geom')
        # print(gdf_tracks.head())
        # print(gdf_tracks['insert_date'].head())
        if len(gdf_tracks) == 0:
            m = folium.Map(location=[0, 0],
                           zoom_start=2, tiles='OpenStreetMap')
        else:
            try:
                gdf_tracks['insert_date'] = gdf_tracks['insert_date'].dt.strftime(
                    '%Y-%m-%d %H:%M:%S')
                gdf_tracks['duration'] = 0
                gdf_tracks['duration'] = (
                    gdf_tracks['end_time'] - gdf_tracks['start_time']).dt.total_seconds()
                gdf_tracks['start_time'] = gdf_tracks['start_time'].dt.strftime(
                    '%Y-%m-%d %H:%M:%S')
                gdf_tracks['end_time'] = gdf_tracks['end_time'].dt.strftime(
                    '%Y-%m-%d %H:%M:%S')
            except Exception:
                pass

            gdf_tracks['type'] = gdf_tracks['type'].fillna('other')
            gdf_tracks['link'] = gdf_tracks['link'].fillna('')
            gdf_tracks['comment'].str.replace('\r\n', '<br>')

            query = "SELECT AVG(ST_Y(ST_Centroid(geom))) AS mean_latitude, AVG(ST_X(ST_Centroid(geom))) AS mean_longitude FROM gpx_tracks t JOIN collection_track ct ON ct.track_id = t.id WHERE ct.collection_id = %s;"
            df_mean = pd.read_sql(query, conn, params=(collection_id,))
            m = folium.Map(location=[df_mean['mean_latitude'].iloc[0],
                           df_mean['mean_longitude'].iloc[0]], zoom_start=8, tiles='OpenStreetMap')

            folium.TileLayer(tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
                             attr='Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                             name='OpenTopoMap',
                             overlay=False).add_to(m)
            folium.TileLayer('Cartodb Positron').add_to(m)
            folium.TileLayer(tiles='https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',
                             attr='&copy; OpenStreetMap contributors',
                             name='OSM Hot',
                             overlay=False).add_to(m)
            folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
                             attr='Google Maps (Route)',
                             name='Google Maps (Route)',
                             overlay=False).add_to(m)
            folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
                             attr='Google Terrain',
                             name='Google Terrain',
                             overlay=False).add_to(m)
            folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                             attr='Google Satellite',
                             name='Google Satellite',
                             overlay=False).add_to(m)

            def style_function(feature):
                return {
                    'color': 'green',
                    'weight': 4,
                    'opacity': 0.8,
                }

            folium.GeoJson(
                gdf_tracks.to_json(),
                style_function=style_function,
                name='Collection Tracks'
            ).add_to(m)
            folium.LayerControl().add_to(m)

    db_session.close()
    return render_template('collection.html', collection=collection, script_map=m.get_root()._repr_html_())


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


@app.route('/api/travel-wishes', methods=['POST'])
def create_travel_wish():
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        data = request.get_json()
        title = data.get('title')
        description = data.get('description')
        region = data.get('region')

        if not title:
            return jsonify({'error': 'Title is required'}), 400

        current_user = db.session.query(User).filter_by(
            uuid=session['user'].get('sub')).first()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404

        new_wish = TravelWish(
            title=title,
            description=description,
            region=region,
            user_id=current_user.id
        )
        db.session.add(new_wish)
        db.session.commit()

        return jsonify({
            'id': new_wish.id,
            'title': new_wish.title,
            'description': new_wish.description,
            'region': new_wish.region
        }), 201
    except Exception as e:
        print(f"Error creating travel wish: {e}")
        return jsonify({'error': 'Failed to create travel wish'}), 500


@app.route('/api/travel-wishes/<int:wish_id>', methods=['GET'])
def get_travel_wish(wish_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        current_user = db.session.query(User).filter_by(
            uuid=session['user'].get('sub')).first()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404

        wish = db.session.query(TravelWish).filter_by(
            id=wish_id, user_id=current_user.id).first()
        if not wish:
            return jsonify({'error': 'Wish not found'}), 404

        return jsonify({
            'id': wish.id,
            'title': wish.title,
            'description': wish.description,
            'region': wish.region
        }), 200
    except Exception as e:
        print(f"Error getting travel wish: {e}")
        return jsonify({'error': 'Failed to get travel wish'}), 500


@app.route('/api/travel-wishes/<int:wish_id>', methods=['PUT'])
def update_travel_wish(wish_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        data = request.get_json()
        current_user = db.session.query(User).filter_by(
            uuid=session['user'].get('sub')).first()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404

        wish = db.session.query(TravelWish).filter_by(
            id=wish_id, user_id=current_user.id).first()
        if not wish:
            return jsonify({'error': 'Wish not found'}), 404

        if 'title' in data:
            wish.title = data['title']
        if 'description' in data:
            wish.description = data['description']
        if 'region' in data:
            wish.region = data['region']

        db.session.commit()

        return jsonify({
            'id': wish.id,
            'title': wish.title,
            'description': wish.description,
            'region': wish.region
        }), 200
    except Exception as e:
        print(f"Error updating travel wish: {e}")
        return jsonify({'error': 'Failed to update travel wish'}), 500


@app.route('/api/travel-wishes/<int:wish_id>', methods=['DELETE'])
def delete_travel_wish(wish_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        current_user = db.session.query(User).filter_by(
            uuid=session['user'].get('sub')).first()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404

        wish = db.session.query(TravelWish).filter_by(
            id=wish_id, user_id=current_user.id).first()
        if not wish:
            return jsonify({'error': 'Wish not found'}), 404

        db.session.delete(wish)
        db.session.commit()

        return jsonify({'message': 'Travel wish deleted successfully'}), 200
    except Exception as e:
        print(f"Error deleting travel wish: {e}")
        return jsonify({'error': 'Failed to delete travel wish'}), 500


# ======================== WAYPOINTS ROUTES ========================

@app.route('/api/waypoints', methods=['GET'])
def get_waypoints():
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        current_user = db.session.query(User).filter_by(
            uuid=session['user'].get('sub')).first()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404

        waypoints = db.session.query(Waypoint).filter_by(
            user_id=current_user.id).all()

        waypoints_data = []
        for wp in waypoints:
            shapely_point = to_shape(wp.geom)
            waypoints_data.append({
                'id': wp.id,
                'description': wp.description,
                'lat': shapely_point.y,
                'lng': shapely_point.x,
                'created_at': wp.created_at.isoformat() if wp.created_at else None
            })

        return jsonify(waypoints_data), 200
    except Exception as e:
        print(f"Error getting waypoints: {e}")
        return jsonify({'error': 'Failed to get waypoints'}), 500


@app.route('/api/waypoints', methods=['POST'])
def create_waypoint():
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        data = request.get_json()
        lat = data.get('lat')
        lng = data.get('lng')
        description = data.get('description', '')

        if lat is None or lng is None:
            return jsonify({'error': 'Latitude and longitude are required'}), 400

        current_user = db.session.query(User).filter_by(
            uuid=session['user'].get('sub')).first()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404

        # Create point geometry
        point = Point(lng, lat)
        wkt = point.wkt

        new_waypoint = Waypoint(
            description=description,
            user_id=current_user.id,
            geom=WKTElement(wkt, srid=4326)
        )
        db.session.add(new_waypoint)
        db.session.commit()

        return jsonify({
            'id': new_waypoint.id,
            'description': new_waypoint.description,
            'lat': lat,
            'lng': lng,
            'created_at': new_waypoint.created_at.isoformat() if new_waypoint.created_at else None
        }), 201
    except Exception as e:
        print(f"Error creating waypoint: {e}")
        return jsonify({'error': 'Failed to create waypoint'}), 500


@app.route('/api/waypoints/<int:waypoint_id>', methods=['GET'])
def get_waypoint(waypoint_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        current_user = db.session.query(User).filter_by(
            uuid=session['user'].get('sub')).first()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404

        waypoint = db.session.query(Waypoint).filter_by(
            id=waypoint_id, user_id=current_user.id).first()
        if not waypoint:
            return jsonify({'error': 'Waypoint not found'}), 404

        shapely_point = to_shape(waypoint.geom)
        return jsonify({
            'id': waypoint.id,
            'description': waypoint.description,
            'lat': shapely_point.y,
            'lng': shapely_point.x,
            'created_at': waypoint.created_at.isoformat() if waypoint.created_at else None
        }), 200
    except Exception as e:
        print(f"Error getting waypoint: {e}")
        return jsonify({'error': 'Failed to get waypoint'}), 500


@app.route('/api/waypoints/<int:waypoint_id>', methods=['PUT'])
def update_waypoint(waypoint_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        data = request.get_json()
        current_user = db.session.query(User).filter_by(
            uuid=session['user'].get('sub')).first()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404

        waypoint = db.session.query(Waypoint).filter_by(
            id=waypoint_id, user_id=current_user.id).first()
        if not waypoint:
            return jsonify({'error': 'Waypoint not found'}), 404

        if 'description' in data:
            waypoint.description = data['description']

        db.session.commit()

        shapely_point = to_shape(waypoint.geom)
        return jsonify({
            'id': waypoint.id,
            'description': waypoint.description,
            'lat': shapely_point.y,
            'lng': shapely_point.x,
            'created_at': waypoint.created_at.isoformat() if waypoint.created_at else None
        }), 200
    except Exception as e:
        print(f"Error updating waypoint: {e}")
        return jsonify({'error': 'Failed to update waypoint'}), 500


@app.route('/api/waypoints/<int:waypoint_id>', methods=['DELETE'])
def delete_waypoint(waypoint_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        current_user = db.session.query(User).filter_by(
            uuid=session['user'].get('sub')).first()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404

        waypoint = db.session.query(Waypoint).filter_by(
            id=waypoint_id, user_id=current_user.id).first()
        if not waypoint:
            return jsonify({'error': 'Waypoint not found'}), 404

        db.session.delete(waypoint)
        db.session.commit()

        return jsonify({'message': 'Waypoint deleted successfully'}), 200
    except Exception as e:
        print(f"Error deleting waypoint: {e}")
        return jsonify({'error': 'Failed to delete waypoint'}), 500


@app.route('/api/waypoints/<int:waypoint_id>/add-to-collection/<int:collection_id>', methods=['POST'])
def add_waypoint_to_collection(waypoint_id, collection_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        current_user = db.session.query(User).filter_by(
            uuid=session['user'].get('sub')).first()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404

        waypoint = db.session.query(Waypoint).filter_by(
            id=waypoint_id, user_id=current_user.id).first()
        if not waypoint:
            return jsonify({'error': 'Waypoint not found'}), 404

        collection = db.session.query(Collection).filter_by(
            id=collection_id, user_id=current_user.id).first()
        if not collection:
            return jsonify({'error': 'Collection not found'}), 404

        if waypoint not in collection.waypoints:
            collection.waypoints.append(waypoint)
            db.session.commit()

        return jsonify({'message': 'Waypoint added to collection successfully'}), 200
    except Exception as e:
        print(f"Error adding waypoint to collection: {e}")
        return jsonify({'error': 'Failed to add waypoint to collection'}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
