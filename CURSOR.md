## GeoWander `leaflet_lab`)

A **Flask web app for sharing and discovering hiking trails** — similar in spirit to AllTrails. The README calls it **GeoWander**; the Docker image and Cloud Run service are named **alltrail-map** / **alltrail**. The repo folder name `leaflet_lab` reflects early map experiments; the product direction is a full trail platform.

### Purpose

Users can upload GPX tracks, browse trails on a map, inspect elevation profiles, organize routes into collections, and plan trips via travel wishlists. The README outlines a broader vision: search/filters, favorites, weather-based time estimates, comments, and multi-format exports.

### Tech stack

| Layer | Choices |

|--------|---------|

| Backend | Flask, Flask-Login, Flask-CORS |

| Database | PostgreSQL + PostGIS on **Aiven** (SQLAlchemy, GeoAlchemy2, Alembic) |

| Geo processing | `gpxpy`, GeoPandas, Shapely |

| Maps | **MapLibre** (primary); templates also exist for Leaflet, Mapbox, Cesium, Folium |

| Auth | Google OAuth |

| Deploy | Docker → **Google Cloud Run**, CI/CD via **Cloud Build** |

| External APIs | Google Maps (geocoding/places), Open-Meteo, Visual Crossing, Geoapify, Foursquare |

### Data model

Core entities in `app/models/domain.py`:

- **Users** — accounts linked to Google login

- **GPXTrack** — trail geometry `LINESTRING`), length, elevation gain/loss, metadata

- **Waypoint** — point features tied to users/collections

- **Collection** — user-owned groups of tracks and waypoints

- **TravelWish** — trip planning wishlists

### Application structure

```

[main.py](http://main.py)              # App factory, home, GPX upload, track pages

app/routes/

  [auth.py](http://auth.py)            # Google login/logout

  [explore.py](http://explore.py)         # Map exploration

  [api.py](http://api.py)             # REST API aggregator

  [tracks.py](http://tracks.py)          # CRUD + search for tracks

  [collections.py](http://collections.py)     # Collection management

  [waypoints.py](http://waypoints.py)       # Waypoint CRUD + place search

  travel_[wishes.py](http://wishes.py)   # Wishlist CRUD

app/utils/[gpxutils.py](http://gpxutils.py)

templates/           # maplibre.html, detail.html, collection.html, etc.

static/js/elevation_profile.js   # Interactive elevation chart synced with map

tests/               # GPX fixtures + API/integration tests

```

### Notable features (implemented or in progress)

- **GPX upload** — parsed and stored with geometry and stats `calculate_elevation_gain`)

- **Elevation profile** — SVG chart with hover tooltip (distance, altitude, cumulative climb, slope) and sync to MapLibre

- **REST API** under `/api` for tracks, collections, waypoints, and travel wishes

- **Multiple map UIs** — experimentation across MapLibre, Leaflet, Mapbox, Cesium

- **Collections & wishlists** — backend routes and dedicated templates

### Run locally

```bash

flask --app [main.py](http://main.py) run --host 0.0.0.0

# or

python -m http.server 8000   # static serving (README)

```

Requires a `.env` with Aiven DB credentials and Google OAuth settings `config.py`).

### Deployment

`Dockerfile` builds a Python 3.12 image; `cloudbuild.yaml` builds, pushes to Artifact Registry, and deploys to Cloud Run `us-central1`).

---

In short: a **trail-sharing platform** built on Flask + PostGIS, centered on GPX ingestion, interactive maps (MapLibre), and user collections — with a large feature roadmap in the README and a working core around upload, storage, API, and map visualization.