from app.models.db import db
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
from shapely.geometry import LineString
from app.models.domain import Base, User, Collection, GPXTrack
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
        'pool_size': 10,
        'max_overflow': 20,
        'pool_timeout': 30
    }
    from app.routes import auth
    app.register_blueprint(auth.bp)
    db.init_app(app)
    return app


app = create_app()
with app.app_context():
    db.create_all()


@app.route('/alltrail')
def alltrail():
    colors = {
        'HIKE': 'green',
        'OFFROAD': 'blue',
        'hiking': 'brown',
        'skiing': 'cyan',
        'other': 'red'}

    def style_function(feature):
        type = feature['properties']['type']
    # print(type)
        return {
            # 'fillColor': "#b92c2c",
            "color": colors.get(type),
            'fillOpacity': 0.5,
            # borders
            'weight': 3,
        }

    def highlight_function(feature):
        type = feature['properties']['type']
    # print(type)
        return {
            'fillColor': '#ffff00',
            "color": "yellow",
            'fillOpacity': 1,
            # borders
            'weight': 5,
        }
    on_click_script = folium.JsCode("""
        function(feature, layer) {
            layer.on('click', function(e) {
                if (window.parent.controlElevation) {
                    window.parent.controlElevation.clear();
                    // Charger les données d'élévation pour ce track
                    var gjl = L.geoJson(layer.toGeoJSON(),{
                        onEachFeature: window.parent.controlElevation.addData(feature)
                        // onEachFeature: window.parent.controlElevation.addData.bind(window.parent.controlElevation)
                    });
                }                                                               
            });
        }
        """)

    zoom_script = """
    $(document).ready(function(){
        ma_carte_unique123.on('zoomend', function() {
            updateUrl(ma_carte_unique123);

        })
    });
        
        
    $(document).ready(function(){
        ma_carte_unique123.on('moveend', function() {
            updateUrl(ma_carte_unique123);
            })
        });
    
        $(document).ready(updateUrl=function(map){
            console.log(map);
            var currentZoom = ma_carte_unique123.getZoom();
            // Example: Hide marker if zoom is less than 10
            // You would need to reference the specific layer object here
            console.log(currentZoom)
            console.log(ma_carte_unique123)
            var bounds = ma_carte_unique123.getBounds();
            var northWest = bounds.getNorthWest(); // {lat: ..., lng: ...}
            var southEast = bounds.getSouthEast(); // {lat: ..., lng: ...}
            var center = map.getCenter();
            var lat = center.lat;
            var lng = center.lng;
            console.log("NW Lat: " + northWest.lat);
            console.log("NW Lng: " + northWest.lng);
            console.log("SE Lat: " + southEast.lat);
            console.log("SE Lng: " + southEast.lng);

            // Get current URL and create URL object
            const url = new URL(window.parent.location.href);

            // 1. Add or update a parameter
            url.searchParams.set('zoom', currentZoom);

            // 2. Add a parameter with multiple values
            url.searchParams.set('filter', 'active');

            // 3. Remove a parameter
            //url.searchParams.delete('old_param');

            url.searchParams.set('lat', center.lat);
            url.searchParams.set('lng', center.lng);

            // Update the browser URL without reload
            window.parent.history.replaceState({}, document.title, url.toString());
        });
    """
    db_session = db.session
    with db_session.connection() as conn:
        gdf_tracks = gpd.GeoDataFrame.from_postgis(
            "SELECT * FROM gpx_tracks", con=conn)

        query = "SELECT AVG(ST_Y(ST_Centroid(geom))) AS mean_latitude, AVG(ST_X(ST_Centroid(geom))) AS mean_longitude FROM gpx_tracks;"
        df_mean = pd.read_sql(query, conn)
        m = folium.Map(
            location=[df_mean['mean_latitude'].iloc[0],
                      df_mean['mean_longitude'].iloc[0]],
            zoom_start=8,
            tiles='OpenStreetMap',
        )
        m.get_root().script.add_child(folium.Element(zoom_script))

        folium.TileLayer(tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
                         attr='Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
                         name="opentopomap",
                         overlay=False).add_to(m)
        folium.TileLayer('Cartodb Positron').add_to(m)
        folium.TileLayer(tiles="https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
                         attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Tiles style by <a href="https://www.hotosm.org/" target="_blank">Humanitarian OpenStreetMap Team</a> hosted by <a href="https://openstreetmap.fr/" target="_blank">OpenStreetMap France</a>',
                         name="OSM Hot",
                         overlay=False).add_to(m)
        folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
                         attr='Google Maps (Route)',
                         name="Google Maps (Route)",
                         overlay=False).add_to(m)
        folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
                         attr='Google Terrain',
                         name="Google Terrain",
                         overlay=False).add_to(m)
        folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                         attr='Google Satellite',
                         name="Google Satellite",
                         overlay=False).add_to(m)

        m._name = "ma_carte"
        m._id = "unique123"
        m.get_root().height = "600px"
        gdf_tracks['insert_date'] = gdf_tracks['insert_date'].dt.strftime(
            '%Y-%m-%d %H:%M:%S')
        gdf_tracks['duration'] = 0
        try:
            gdf_tracks['duration'] = (
                gdf_tracks['end_time'] - gdf_tracks['start_time']).dt.total_seconds()
            gdf_tracks['start_time'] = gdf_tracks['start_time'].dt.strftime(
                '%Y-%m-%d %H:%M:%S')
            gdf_tracks['end_time'] = gdf_tracks['end_time'].dt.strftime(
                '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"Error formatting start_time or end_time: {e}")
        gdf_tracks['type'] = gdf_tracks['type'].fillna('other')
        gdf_tracks['link'] = gdf_tracks['link'].fillna('')
        gdf_tracks['comment'].str.replace('\r\n', '<br>')

        # split par type de track pour coloriser
        for type in gdf_tracks['type'].unique():
            tooltip = folium.GeoJsonTooltip(
                fields=["name", "type", "length", "elevation_gain", "elevation_loss", "insert_date",
                        "start_point_geo", "start_time", "end_time", "link", "duration", "comment"],
                # aliases=["State:", "2015 Median Income(USD):", "Median % Change:"],
                localize=True,
                sticky=False,
                labels=True,
                style="""
                    background-color: #F0EFEF;
                    border: 2px solid black;
                    border-radius: 3px;
                    box-shadow: 3px;
                """,
                max_width=800,
            )
            popup = folium.GeoJsonPopup(
                fields=["name", "type", "length", "elevation_gain", "elevation_loss", "insert_date",
                        "start_point_geo", "start_time", "end_time", "link", "duration", "comment"],
                # aliases=["State:", "2015 Median Income(USD):", "Median % Change:"],
                localize=True,
                sticky=False,
                labels=True,
                style="""
                    background-color: #F0EFEF;
                    border: 2px solid black;
                    border-radius: 3px;
                    box-shadow: 3px;
                """,
                max_width=800,
            )

            gj = folium.GeoJson(gdf_tracks[(gdf_tracks['type'] == type)].to_json(),
                                style_function=style_function,
                                highlight_function=highlight_function,
                                tooltip=tooltip,
                                popup=popup,
                                name=type,
                                on_each_feature=on_click_script,
                                zoom_on_click=True)
            gj.add_to(m)
        folium.LayerControl().add_to(m)

        user_collections = []
        if 'user' in session:
            current_user = db.session.query(User).filter_by(
                uuid=session['user'].get('sub')).first()
            if current_user:
                user_collections = current_user.collections

    db_session.close()

    return render_template(
        'trails.html',
        script_map=m.get_root()._repr_html_(),
        track_list=gdf_tracks.to_dict('records'),
        user_collections=user_collections
    )


@app.route("/find_tracks")
def find_tracks():
    NW_lat = request.args.get('NW_lat')
    NW_lon = request.args.get('NW_lon')
    SE_lat = request.args.get('SE_lat')
    SE_lon = request.args.get('SE_lon')
    print(request.args)
    category = request.args.get('category')
    db_session = db.session
    with db_session.connection() as conn:

        # Filter by bounding box using SQL
        sql = f"""
        SELECT *
        FROM gpx_tracks
        WHERE ST_X(ST_StartPoint(geom)) BETWEEN {NW_lon} AND {SE_lon} 
        AND ST_Y(ST_StartPoint(geom)) BETWEEN {SE_lat} AND {NW_lat}
        """
        # print(sql)
        gdf_tracks = gpd.GeoDataFrame.from_postgis(sql, con=conn)
        # print(gdf_tracks)
        if gdf_tracks.empty:
            return gdf_tracks.to_json()

        gdf_tracks['insert_date'] = gdf_tracks['insert_date'].dt.strftime(
            '%Y-%m-%d %H:%M:%S')
        gdf_tracks['duration'] = 0
        try:
            gdf_tracks['duration'] = (
                gdf_tracks['end_time'] - gdf_tracks['start_time']).dt.total_seconds()
            gdf_tracks['start_time'] = gdf_tracks['start_time'].dt.strftime(
                '%Y-%m-%d %H:%M:%S')
            gdf_tracks['end_time'] = gdf_tracks['end_time'].dt.strftime(
                '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"Error formatting start_time or end_time: {e}")
        gdf_tracks['type'] = gdf_tracks['type'].fillna('other')
        gdf_tracks['link'] = gdf_tracks['link'].fillna('')
        gdf_tracks['comment'].str.replace('\r\n', '<br>')

        return gdf_tracks.to_json()


@app.route("/")
def index():
    # return redirect("/alltrail")
    return render_template("index.html")


@app.route("/folium")
def folium_map():
    import geopandas as gpd
    import folium
    from geojson_length import calculate_distance, Unit
    engine = persistence.get_engine()
    gdf = gpd.read_postgis(
        "SELECT name, geom FROM gpx_tracks", con=engine, geom_col='geom')

    # S'assurer que le CRS est EPSG:4326
    if gdf.crs.to_string() != 'EPSG:4326':
        gdf = gdf.to_crs('EPSG:4326')

    # 2. Créer la carte avec Folium
    # On centre la carte sur la moyenne des coordonnées
    m = folium.Map(location=[gdf.geometry.centroid.y.mean(
    ), gdf.geometry.centroid.x.mean()], zoom_start=10)

    for idx, row in gdf.iterrows():
        geom = row['geom']
        name = row['name']
        print(f"Processing track: {name}, Geometry type: {geom.geom_type}")
        # Ajouter les données géographiques sous forme de GeoJSON
        if geom.geom_type == 'LineString':
            # folium.PolyLine(locations=[(point.y, point.x) for point in geom.coords], color='blue', weight=5, opacity=0.7, tooltip=name).add_to(m)
            # line = Feature(geometry=geom, properties={"name": name})
            tooltip = name + '<br>' + f"Length: {geom.length:.2f} km" + ' <br>   ' + str(
                calculate_distance(geom, Unit.kilometers)*100) + f"Type: {geom.geom_type}"
            folium.GeoJson(geom, tooltip=folium.Tooltip(
                text=tooltip), color='red').add_to(m)
        elif geom.geom_type == 'Point':
            folium.Marker(location=(geom.y, geom.x), tooltip=name).add_to(m)

    # 3. Rendre la carte HTML dans Flask
    return render_template('folium.html', map=m._repr_html_())


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/elevation', methods=['GET'])
def elevation():
    from geoalchemy2 import functions
    import shapely.geometry
    import geojson
    session = db.session
    # geojson_qry = session.query(functions.ST_AsGeoJSON(GPXTrack.geom)).filter(
    qry = session.query(GPXTrack).filter(
        GPXTrack.id == 34
    )
    trx = qry[0]
    feature = geojson.Feature(
        id=1,
        geometry=shapely.geometry.mapping(to_shape(trx.geom)),
        properties={"name": trx.name}
    )
    collection = geojson.FeatureCollection([feature])
    return render_template('elevation.html', geojson=collection)


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

        return redirect("/alltrail")


@app.route('/search', methods=['GET'])
def autocomplete():
    # Retrieve the search term sent by jQuery
    search = request.args.get('term')
    print("search : " + search)
    results = ["titi", "tata", "toto"]

    # Return JSON response
    return jsonify(results=results)


@app.route('/api/collections', methods=['POST'])
def create_collection():
    """Create a new collection for the current user"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Collection name is required'}), 400

    try:
        # Get user ID from database
        user_session = db.session
        user = user_session.query(User).filter_by(
            name=session['user']['name']).first()

        if not user:
            # Create user if doesn't exist
            user = User(name=session['user']['name'], email=session['user']
                        ['email'], uuid=session['user']['sub'])
            user_session.add(user)
            user_session.commit()
        pic_url = requests.get(
            f"https://api.unsplash.com/photos/random/?query={data['name']}&client_id=Y1Ri-AxBBUpySRvlADwGX-CTWCY9yZv0mJ3peT2_2VE").json()

        # Create new collection
        new_collection = Collection(
            name=data['name'],
            user_id=user.id,
            description=data.get('description', ''),
            pic_url=pic_url["urls"]["small_s3"]
        )

        user_session.add(new_collection)
        user_session.commit()

        result = {
            'id': new_collection.id,
            'name': new_collection.name,
            'user_id': new_collection.user_id,
            'description': new_collection.description
        }

        user_session.close()
        return jsonify(result), 201

    except Exception as e:
        print(f"Error creating collection: {e}")
        print(traceback.format_exc())

        return jsonify({'error': 'Failed to create collection'}), 500


@app.route('/api/collections/<int:collection_id>', methods=['DELETE'])
def delete_collection(collection_id):
    """Delete a collection for the current user"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        # Get user ID from database
        user_session = db.session
        user = user_session.query(User).filter_by(
            name=session['user']['name']).first()

        if not user:
            user_session.close()
            return jsonify({'error': 'User not found'}), 404

        # Find the collection
        collection = user_session.query(Collection).filter_by(
            id=collection_id,
            user_id=user.id
        ).first()

        if not collection:
            user_session.close()
            return jsonify({'error': 'Collection not found'}), 404

        # Delete the collection
        user_session.delete(collection)
        user_session.commit()

        user_session.close()
        return jsonify({'message': 'Collection deleted successfully'}), 200

    except Exception as e:
        print(f"Error deleting collection: {e}")
        return jsonify({'error': 'Failed to delete collection'}), 500


@app.route('/api/collections/<int:collection_id>/tracks', methods=['POST'])
def add_track_to_collection(collection_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    track_id = data.get('track_id') if data else None
    if not track_id:
        return jsonify({'error': 'track_id is required'}), 400

    try:
        current_user = db.session.query(User).filter_by(
            uuid=session['user'].get('sub')).first()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404

        collection = db.session.query(Collection).filter_by(
            id=collection_id, user_id=current_user.id).first()
        if not collection:
            return jsonify({'error': 'Collection not found'}), 404

        track = db.session.query(GPXTrack).filter_by(id=track_id).first()
        if not track:
            return jsonify({'error': 'Trail not found'}), 404

        if track not in collection.tracks:
            collection.tracks.append(track)
            db.session.commit()

        return jsonify({'message': 'Trail added to collection successfully'}), 201
    except Exception as e:
        print(f"Error adding track to collection: {e}")
        print(traceback.format_exc())
        return jsonify({'error': 'Failed to add trail to collection'}), 500


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
        print(gdf_tracks.head())
        print(gdf_tracks['insert_date'].head())
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
