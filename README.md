# GeoWander - A web app to share and discover hiking trails around the world

local server : 
python -m http.server 8000
flask --app main.py run --host 0.0.0.0

persistence : (geo)alchemy sur postgre+gis (AIVEN) et geopandas
authent : google + flask-login
ergonomie : leaflet
recherche de lieux : google places api

build/run : docker build -t alltrail-map . && docker run -p 5000:5000 alltrail-map
deployment : google cloud run + cloud build

Modèle : 
- traces : id, name, type, owner, visibility, gpx_url, tags, languages, tags, length, duration, elevation_gain, location, popularity, pictures, start locality (administrative area), end locality, created_at, updated_at, comments
- users : id, name, email, login_type (google/okta), password
- waypoints : id, track_id, name, description, lat, lon, elevation, timestamp, tags, languages, pictures, administrative area, created_at, updated_at, comments
- collections : id, name, owner, visibility, tracks, waypoints
- travel wishlist : id, user_id, name, description, tracks, waypoints
- travel : set of tracks and waypoints with a defined order

Specs : 
- user can upload gpx file and it will be parsed and stored in the database
- the elevation profile is available for each track and can be visualized on the track page
- user can view their tracks on a map
- user can flag a track/waypoint as favorite
- filters : type, collection, tags, languages, length, duration, elevation gain, location
- search : by name, description, tags, languages
- 3D/2D visualization
- Use maplibre
- user can download a track as gpx file or other formats
- user can create/delete/update collections of tracks and waypoints
- user can create/delete/update travel wishlists
- user can create/delete/update travels (ordered set of tracks and waypoints)
- user can get yearly weather forecast for a track based on historical data and weather models
- user can get estimated time to complete a track based on historical data and weather models

Site map : 
- home page : list of tracks, search bar, filters, login/signup
- track page : map with the track, details (length, duration, elevation gain, location), waypoints, comments
- collections page : list of collections, details of each collection, tracks in the collection
- travel wishlist page : list of wishlists, details of each wishlist, tracks in the wishlist
- user profile page : user details, list of tracks, collections, wishlists

Run : 
- deploy on google cloud run
- use cloud build for CI/CD
- genrate availability report with lighthouse and webpagetest
- monitor with google cloud monitoring and error reporting

Used APIs :
- google maps api for geocoding and places search