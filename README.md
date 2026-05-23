# My Alltrail Map

local server : 
python -m http.server 8000
flask --app main.py run --host 0.0.0.0

persistence : (geo))alchemy sur postgre+gis (AIVEN)
authent : google + flask-login
ergonomie : leaflet
recherche de lieux : google places api

build/run : docker build -t alltrail-map . && docker run -p 5000:5000 alltrail-map
deployment : google cloud run + cloud build


Specs : 
- gestion des collections 
- nom du parcours
- type de parcours
- propriétaire
- visibilité (pub/priv)
- login (google ou okta)
- gpx => add from url ou upload
- put tag on trail
- gestion des langues sur la carte
