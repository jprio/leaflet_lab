from flask import Flask, render_template,make_response, redirect, request, session,g, flash, url_for, Blueprint
from flask_cors import CORS, cross_origin
from flask_leaflet import Leaflet
from flask_leaflet import Map
import folium
from folium import Element

import requests
import json
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
import os
from werkzeug.utils import secure_filename
import gpxpy
import pandas as pd
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry, WKTElement
from shapely.geometry import LineString
from app.models.domain import Base, User, Collection, Trail, GPXTrack
import  app.models .persistence as persistence
import geopandas as gpd
from geoalchemy2.shape import to_shape
from sqlalchemy import select, func
from app.utils.gpxutils import calculate_elevation_gain
from flask_sqlalchemy import SQLAlchemy
import geocoder

ALLOWED_EXTENSIONS = {'gpx', 'tcx', 'fit', 'csv'}

db = SQLAlchemy(model_class=Base)

def create_app():
    import app.models as models, app.routes as routes

    app = Flask(__name__, static_url_path='', 
            static_folder='static')
    CORS(app) 

    leaflet = Leaflet()
    leaflet.init_app(app)
    models.init_app(app)
    routes.init_app(app)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)
    app.secret_key="123"
    app.config["SQLALCHEMY_DATABASE_URI"] = f'postgresql://{os.environ["AIVEN_USERNAME"]}:{os.environ["AIVEN_PASSWORD"]}@{os.environ["AIVEN_HOST"]}:{os.environ["AIVEN_PORT"]}/{os.environ["AIVEN_DBNAME"]}?sslmode=require'
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_timeout': 30
    }
    from app.routes import auth
    app.register_blueprint(auth.bp)
    print(app.url_map)
    db.init_app(app)
    return app

app = create_app()

@app.route('/alltrail')
def alltrail():
    colors={
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
            #borders
            'weight': 3,
        }
    def highlight_function(feature):
        type = feature['properties']['type']
    # print(type)
        return {
            'fillColor': '#ffff00',
            "color": "yellow",
            'fillOpacity': 1,
            #borders
            'weight': 5,
        }
    tooltip = folium.GeoJsonTooltip(
        fields=["name", "type", "length","elevation_gain", "elevation_loss","insert_date", "start_point_geo"],
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

    session = db.session
    with session.connection() as conn:
        gdf_tracks = gpd.GeoDataFrame.from_postgis("SELECT * FROM gpx_tracks", con=session.connection())
        
        query = "SELECT AVG(ST_Y(ST_Centroid(geom))) AS mean_latitude, AVG(ST_X(ST_Centroid(geom))) AS mean_longitude FROM gpx_tracks;"
        df_mean = pd.read_sql(query, session.connection())
        m = folium.Map( location=[df_mean['mean_latitude'].iloc[0], df_mean['mean_longitude'].iloc[0]], zoom_start=8, tiles='OpenStreetMap')
        m._name = "ma_carte"
        m._id = "unique123"
        m.get_root().height = "600px"
        gdf_tracks['insert_date'] = gdf_tracks['insert_date'].dt.strftime('%Y-%m-%d %H:%M:%S')
        gj=folium.GeoJson(gdf_tracks.to_json(), 
                          style_function=style_function,
                          highlight_function=highlight_function,
                          start_stop_colors=("green", "red"),
                          tooltip=tooltip, 
                          on_each_feature=on_click_script,
                          zoom_on_click=True)
        gj.add_to(m)
    session.close()
    return render_template('trails.html', script_map=m.get_root()._repr_html_(), track_list=gdf_tracks.to_dict('records'))


@app.route('/home')
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
    session['user']=info
    session.permanent = True
    print(session['user'])
    return redirect('/')


@app.route("/")
def map():
    response=make_response(render_template("index.html"))
    return response


@app.route("/folium")
def folium_map():
    import geopandas as gpd
    import folium
    from geojson_length import calculate_distance, Unit 
    engine = persistence.get_engine()
    gdf = gpd.read_postgis("SELECT name, geom FROM gpx_tracks", con=engine, geom_col='geom')

    # S'assurer que le CRS est EPSG:4326
    if gdf.crs.to_string() != 'EPSG:4326':
        gdf = gdf.to_crs('EPSG:4326')

    # 2. Créer la carte avec Folium
    # On centre la carte sur la moyenne des coordonnées
    m = folium.Map(location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom_start=10)

    for idx, row in gdf.iterrows():
        geom = row['geom']
        name = row['name']
        print(f"Processing track: {name}, Geometry type: {geom.geom_type}")
        # Ajouter les données géographiques sous forme de GeoJSON
        if geom.geom_type == 'LineString':
            # folium.PolyLine(locations=[(point.y, point.x) for point in geom.coords], color='blue', weight=5, opacity=0.7, tooltip=name).add_to(m)
            # line = Feature(geometry=geom, properties={"name": name})
            tooltip = name + '<br>' + f"Length: {geom.length:.2f} km" + ' <br>   ' + str(calculate_distance(geom, Unit.kilometers)*100) + f"Type: {geom.geom_type}"
            folium.GeoJson(geom, tooltip=folium.Tooltip(text=tooltip), color='red').add_to(m)
        elif geom.geom_type == 'Point':
            folium.Marker(location=(geom.y, geom.x), tooltip=name).add_to(m)

    # 3. Rendre la carte HTML dans Flask
    return render_template('folium.html', map=m._repr_html_())

@app.route("/leaflet")
def leaflet():
    my_map = Map('my-map', center=[-41.139416, -73.025431], zoom=16)
    return render_template('leaflet.html', my_map=my_map)


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
    trx=qry[0]
    feature = geojson.Feature(
            id=1,
            geometry=shapely.geometry.mapping(to_shape(trx.geom)),
            properties={"name": trx.name}
        )
    collection = geojson.FeatureCollection([feature])
    return render_template('elevation.html', geojson=collection)


@app.route('/upload', methods = ['POST'])
def upload_file():
    owner = session['user']['sub']
    print(request.form)
    engine = persistence.get_engine()
    # check if the post request has the file part
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    file = request.files['file']
    type=request.form.get('activity_type')
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

            
            # Calculate 3D distance in meters
            distance_3d = track.length_3d()
            print(f"Track: {track.name}, Distance: {distance_3d:.2f} meters")
            
            # Calculate 2D distance
            distance_2d = track.length_2d()
            print(f"Track: {track.name}, 2D Distance: {distance_2d:.2f} meters")
            # elevation gain
            elevation_gain, elevation_loss = calculate_elevation_gain(gpx)
            print(f"Track: {track.name}, Elevation Gain: {elevation_gain:.2f} meters")
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
                        point= segment.points[0]
                        print ('Start at ({0},{1}) -> {2}'.format(point.latitude, point.longitude, point.elevation))

            g = geocoder.google([start_point.latitude, start_point.longitude], method='reverse', key="AIzaSyArCKGOcBrg3Scbd3ufSF9511wsn1-_uVo")
            print(g.json)
            # print( g.country_long +">" + g.state_long + ">" + g.county + ">" + g.city)
            start_point_geo={'country': g.country_long, 'state': g.state_long, 'county': g.county, 'city': g.city}

            points = [(point.longitude, point.latitude, point.elevation) for segment in track.segments for point in segment.points]
            line_string = LineString(points)
            
            # Convert to WKT for insertion
            wkt = line_string.wkt
            try:
                new_track = GPXTrack(name=track.name, geom=WKTElement(wkt, srid=4326)
                                     , owner=owner
                                     , type=type
                                     , elevation_gain=elevation_gain
                                     , elevation_loss=elevation_loss
                                     , insert_date=func.now()
                                     , length=track.length_3d()
                                     , start_point_geo=start_point_geo)
                sess.add(new_track)
                print(f"Inserted track: {track.name} with {len(points)} points.")
                sess.commit()    
                sess.close()
            except Exception as e:  
                print(f"Error inserting track: {track.name}, Error: {e}")
                sess.rollback()
                sess.close()            
        for waypoint in gpx.waypoints:
            print ('waypoint {0} -> ({1},{2})'.format(waypoint.name, waypoint.latitude, waypoint.longitude))

        for route in gpx.routes:
            print ('Route:')

        return redirect("/alltrail")

if __name__ == "__main__":
    # app.run()
    app.run(host="0.0.0.0", port=5000, debug=True)