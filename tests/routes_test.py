import os
import sys
from unittest.mock import MagicMock, patch

# Set mock env variables so main.py doesn't crash on import
os.environ['AIVEN_USERNAME'] = 'mock'
os.environ['AIVEN_PASSWORD'] = 'mock'
os.environ['AIVEN_HOST'] = 'localhost'
os.environ['AIVEN_PORT'] = '5432'
os.environ['AIVEN_DBNAME'] = 'mock'
os.environ['GOOGLE_CLIENT_ID'] = 'mock_id'
os.environ['GOOGLE_CLIENT_SECRET'] = 'mock_secret'
os.environ['GOOGLE_REDIRECT_URI'] = 'http://localhost/auth/home'
os.environ['GEOAPIFY_API_KEY'] = 'mock_geoapify_key'

# Mock SQLAlchemy.create_all on import to prevent actual database connection attempt
from flask_sqlalchemy import SQLAlchemy
real_create_all = SQLAlchemy.create_all
SQLAlchemy.create_all = MagicMock()

# Import the application creator
import main
from main import create_app
from app.models.domain import db, User, Collection, GPXTrack, TravelWish, Waypoint

import unittest
import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from sqlalchemy import event

# Set up SQLite custom functions to mimic PostGIS spatial functions
@event.listens_for(db.engine, "connect")
def register_sqlite_functions(dbapi_connection, connection_record):
    import sqlite3
    if isinstance(dbapi_connection, sqlite3.Connection):
        # Mock PostGIS functions for standard SQLite queries
        dbapi_connection.create_function("ST_GeomFromText", 2, lambda wkt, srid: wkt)
        dbapi_connection.create_function("ST_StartPoint", 1, lambda geom: geom)
        dbapi_connection.create_function("ST_X", 1, lambda geom: 0.0)
        dbapi_connection.create_function("ST_Y", 1, lambda geom: 0.0)
        dbapi_connection.create_function("ST_AsBinary", 1, lambda geom: geom)


class RoutesTestCase(unittest.TestCase):

    def setUp(self):
        # Configure app for in-memory testing
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
        self.app.secret_key = 'test_secret_key'

        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

        # Run database creation against the sqlite engine
        real_create_all(db)

        # Seed database with a test user
        self.user = User(
            name="Test User",
            email="test@example.com",
            uuid="test-uuid"
        )
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login(self):
        with self.client.session_transaction() as sess:
            sess['user'] = {
                'sub': 'test-uuid',
                'name': 'Test User',
                'email': 'test@example.com'
            }

    # ======================== AUTH ROUTES ========================

    def test_auth_login(self):
        response = self.client.get('/auth/login')
        self.assertEqual(response.status_code, 302)
        self.assertIn('accounts.google.com', response.headers['Location'])

    def test_auth_logout(self):
        self.login()
        response = self.client.get('/auth/logout')
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertNotIn('user', sess)

    def test_auth_me_unauthorized(self):
        response = self.client.get('/auth/me')
        self.assertEqual(response.status_code, 302)

    def test_auth_me_authorized(self):
        self.login()
        response = self.client.get('/auth/me')
        self.assertEqual(response.status_code, 200)

    # ======================== EXPLORE ROUTES ========================

    def test_explore_map(self):
        response = self.client.get('/explore/map')
        self.assertEqual(response.status_code, 200)

    # ======================== WAYPOINTS ROUTES ========================

    @patch('geoalchemy2.shape.to_shape', return_value=Point(1.0, 2.0))
    def test_get_waypoints(self, mock_to_shape):
        self.login()
        # Add a dummy waypoint
        wp = Waypoint(description="Test WP", user_id=self.user.id, geom="POINT(1.0 2.0)")
        db.session.add(wp)
        db.session.commit()

        response = self.client.get('/api/waypoints')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['description'], 'Test WP')

    def test_create_waypoint(self):
        self.login()
        response = self.client.post('/api/waypoints', json={
            'lat': 48.8566,
            'lng': 2.3522,
            'description': 'Paris'
        })
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['description'], 'Paris')

    @patch('geoalchemy2.shape.to_shape', return_value=Point(2.3522, 48.8566))
    def test_get_waypoint(self, mock_to_shape):
        self.login()
        wp = Waypoint(description="Paris", user_id=self.user.id, geom="POINT(2.3522 48.8566)")
        db.session.add(wp)
        db.session.commit()

        response = self.client.get(f'/api/waypoints/{wp.id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['description'], 'Paris')

    @patch('geoalchemy2.shape.to_shape', return_value=Point(2.3522, 48.8566))
    def test_update_waypoint(self, mock_to_shape):
        self.login()
        wp = Waypoint(description="Old", user_id=self.user.id, geom="POINT(2.3522 48.8566)")
        db.session.add(wp)
        db.session.commit()

        response = self.client.put(f'/api/waypoints/{wp.id}', json={'description': 'New'})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['description'], 'New')

    def test_delete_waypoint(self):
        self.login()
        wp = Waypoint(description="To Delete", user_id=self.user.id, geom="POINT(2.3522 48.8566)")
        db.session.add(wp)
        db.session.commit()

        response = self.client.delete(f'/api/waypoints/{wp.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(db.session.query(Waypoint).filter_by(id=wp.id).first())

    @patch('requests.get')
    def test_search_places(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"features": [{"properties": {"name": "Supermarket"}}]}
        
        response = self.client.get('/api/search_places?NW_lat=1&NW_lon=2&SE_lat=3&SE_lon=4')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['features'][0]['properties']['name'], 'Supermarket')

    # ======================== COLLECTIONS ROUTES ========================

    @patch('requests.get')
    def test_create_collection(self, mock_get):
        self.login()
        mock_get.return_value.json.return_value = {"urls": {"small_s3": "http://unsplash.com/test.jpg"}}
        
        response = self.client.post('/api/collections', json={
            'name': 'Summer Hikes',
            'description': 'Fun trails'
        })
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['name'], 'Summer Hikes')

    def test_list_collections(self):
        self.login()
        col = Collection(name="Winter Trails", description="Cold", pic_url="http://url.jpg", user_id=self.user.id)
        db.session.add(col)
        db.session.commit()

        response = self.client.get('/api/collections')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'Winter Trails')

    def test_get_collection_infos(self):
        self.login()
        col = Collection(name="Trails", description="Desc", pic_url="http://pic.jpg", user_id=self.user.id)
        db.session.add(col)
        db.session.commit()

        response = self.client.get(f'/api/collections/info/{col.id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['name'], 'Trails')

    def test_delete_collection(self):
        self.login()
        col = Collection(name="Delete Me", description="Desc", pic_url="http://pic.jpg", user_id=self.user.id)
        db.session.add(col)
        db.session.commit()

        response = self.client.delete(f'/api/collections/{col.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(db.session.query(Collection).filter_by(id=col.id).first())

    def test_add_track_to_collection(self):
        self.login()
        col = Collection(name="Col", description="Desc", pic_url="http://pic.jpg", user_id=self.user.id)
        track = GPXTrack(name="Track", geom="LINESTRING(0 0, 1 1)")
        db.session.add_all([col, track])
        db.session.commit()

        response = self.client.post(f'/api/collections/{col.id}/tracks', json={'track_id': track.id})
        self.assertEqual(response.status_code, 201)
        self.assertIn(track, col.tracks)

    def test_remove_track_from_collection(self):
        self.login()
        col = Collection(name="Col", description="Desc", pic_url="http://pic.jpg", user_id=self.user.id)
        track = GPXTrack(name="Track", geom="LINESTRING(0 0, 1 1)")
        col.tracks.append(track)
        db.session.add_all([col, track])
        db.session.commit()

        response = self.client.delete(f'/api/collections/{col.id}/tracks/{track.id}')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(track, col.tracks)

    def test_add_waypoint_to_collection(self):
        self.login()
        col = Collection(name="Col", description="Desc", pic_url="http://pic.jpg", user_id=self.user.id)
        wp = Waypoint(description="WP", user_id=self.user.id, geom="POINT(0 0)")
        db.session.add_all([col, wp])
        db.session.commit()

        response = self.client.post(f'/api/waypoints/{wp.id}/add-to-collection/{col.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(wp, col.waypoints)

    @patch('geopandas.GeoDataFrame.from_postgis')
    def test_get_collection_tracks(self, mock_from_postgis):
        self.login()
        col = Collection(name="Col", description="Desc", pic_url="http://pic.jpg", user_id=self.user.id)
        db.session.add(col)
        db.session.commit()

        # Mock GeoDataFrame response
        mock_df = gpd.GeoDataFrame({
            'id': [1],
            'name': ['Test Track'],
            'owner': ['test-uuid'],
            'type': ['hiking'],
            'link': ['http://link.com'],
            'comment': ['Nice track'],
            'insert_date': [pd.Timestamp('2026-06-24 10:00:00')],
            'start_time': [pd.Timestamp('2026-06-24 10:00:00')],
            'end_time': [pd.Timestamp('2026-06-24 12:00:00')]
        }, geometry=[Point(0, 0)])
        mock_from_postgis.return_value = mock_df

        response = self.client.get(f'/api/collection_tracks/{col.id}')
        self.assertEqual(response.status_code, 200)

    # ======================== TRACKS ROUTES ========================

    @patch('geopandas.GeoDataFrame.from_postgis')
    def test_find_tracks(self, mock_from_postgis):
        # Mock GeoDataFrame response
        mock_df = gpd.GeoDataFrame({
            'id': [1],
            'name': ['Test Track'],
            'owner': ['test-uuid'],
            'type': ['hiking'],
            'link': ['http://link.com'],
            'comment': ['Nice track'],
            'insert_date': [pd.Timestamp('2026-06-24 10:00:00')],
            'start_time': [pd.Timestamp('2026-06-24 10:00:00')],
            'end_time': [pd.Timestamp('2026-06-24 12:00:00')]
        }, geometry=[Point(0, 0)])
        mock_from_postgis.return_value = mock_df

        response = self.client.get('/api/find_tracks?NW_lat=1&NW_lon=2&SE_lat=3&SE_lon=4')
        self.assertEqual(response.status_code, 200)

    def test_update_track(self):
        self.login()
        track = GPXTrack(name="Old Name", owner="test-uuid", geom="LINESTRING(0 0, 1 1)")
        db.session.add(track)
        db.session.commit()

        response = self.client.put(f'/api/tracks/{track.id}', json={'name': 'New Name'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(track.name, 'New Name')

    @patch('geopandas.GeoDataFrame.from_postgis')
    def test_get_track(self, mock_from_postgis):
        self.login()
        # Mock GeoDataFrame response
        mock_df = gpd.GeoDataFrame({
            'id': [1],
            'name': ['Test Track'],
            'owner': ['test-uuid'],
            'type': ['hiking'],
            'link': ['http://link.com'],
            'comment': ['Nice track'],
            'insert_date': [pd.Timestamp('2026-06-24 10:00:00')],
            'start_time': [pd.Timestamp('2026-06-24 10:00:00')],
            'end_time': [pd.Timestamp('2026-06-24 12:00:00')]
        }, geometry=[Point(0, 0)])
        mock_from_postgis.return_value = mock_df

        response = self.client.get('/api/tracks/1')
        self.assertEqual(response.status_code, 200)

    def test_delete_track(self):
        self.login()
        track = GPXTrack(name="Old Name", owner="test-uuid", geom="LINESTRING(0 0, 1 1)")
        db.session.add(track)
        db.session.commit()

        response = self.client.delete(f'/api/tracks/{track.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(db.session.query(GPXTrack).filter_by(id=track.id).first())

    # ======================== TRAVEL WISHES ROUTES ========================

    def test_create_travel_wish(self):
        self.login()
        response = self.client.post('/api/travel-wishes', json={
            'title': 'Japan',
            'description': 'Tokyo trip',
            'region': 'Asia'
        })
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['title'], 'Japan')

    def test_get_travel_wish(self):
        self.login()
        wish = TravelWish(title="Norway", description="Fjords", region="Europe", user_id=self.user.id)
        db.session.add(wish)
        db.session.commit()

        response = self.client.get(f'/api/travel-wishes/{wish.id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['title'], 'Norway')

    def test_update_travel_wish(self):
        self.login()
        wish = TravelWish(title="Norway", description="Fjords", region="Europe", user_id=self.user.id)
        db.session.add(wish)
        db.session.commit()

        response = self.client.put(f'/api/travel-wishes/{wish.id}', json={'title': 'Norway & Sweden'})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['title'], 'Norway & Sweden')

    def test_delete_travel_wish(self):
        self.login()
        wish = TravelWish(title="Norway", description="Fjords", region="Europe", user_id=self.user.id)
        db.session.add(wish)
        db.session.commit()

        response = self.client.delete(f'/api/travel-wishes/{wish.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(db.session.query(TravelWish).filter_by(id=wish.id).first())


if __name__ == '__main__':
    unittest.main()
