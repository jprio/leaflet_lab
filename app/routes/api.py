from dataclasses import dataclass, asdict
import requests
import traceback
from flask import jsonify
import geopandas as gpd
from flask import (
    Blueprint, request, g, redirect, url_for, flash, render_template, session
)
import json
from app.models.domain import db
from app.models.domain import User, Collection, GPXTrack, TravelWish, Waypoint
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import Point

bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/find_tracks')
def find_tracks():
    NW_lat = request.args.get('NW_lat')
    NW_lon = request.args.get('NW_lon')
    SE_lat = request.args.get('SE_lat')
    SE_lon = request.args.get('SE_lon')
    category = request.args.get('category')
    db_session = db.session
    with db_session.connection() as conn:

        sql = f"""
        SELECT *
        FROM gpx_tracks
        WHERE ST_X(ST_StartPoint(geom)) BETWEEN {NW_lon} AND {SE_lon}
        AND ST_Y(ST_StartPoint(geom)) BETWEEN {SE_lat} AND {NW_lat}
        """
        gdf_tracks = gpd.GeoDataFrame.from_postgis(sql, con=conn)
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
        gdf_tracks['comment'].str.replace('\\r\\n', '<br>')
        print(gdf_tracks)
        return gdf_tracks.to_json()


@bp.route('/search_places', methods=['GET'])
def search_places():
    from requests.structures import CaseInsensitiveDict

    NW_lat = request.args.get('NW_lat')
    NW_lon = request.args.get('NW_lon')
    SE_lat = request.args.get('SE_lat')
    SE_lon = request.args.get('SE_lon')
    url = f"https://api.geoapify.com/v2/places?categories=commercial.supermarket&filter=rect%3A10.716463143326969%2C48.755151258420966%2C10.835314015356737%2C48.680903341613316&limit=20&apiKey={os.getenv('GEOAPIFY_API_KEY')}"

    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json"

    resp = requests.get(url, headers=headers)
    print(resp.text)
    return jsonify(resp.json())


@bp.route('/collections', methods=['POST'])
def create_collection():
    """Create a new collection for the current user"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Collection name is required'}), 400

    try:
        user_session = db.session
        user = user_session.query(User).filter_by(
            name=session['user']['name']).first()

        if not user:
            user = User(name=session['user']['name'], email=session['user']
                        ['email'], uuid=session['user']['sub'])
            user_session.add(user)
            user_session.commit()
        pic_url = requests.get(
            f"https://api.unsplash.com/photos/random/?query={data['name']}&client_id=Y1Ri-AxBBUpySRvlADwGX-CTWCY9yZv0mJ3peT2_2VE").json()
        print(f"pic url : {pic_url} for {data['name']}")
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


@bp.route('/collections/info/<int:collection_id>', methods=['GET'])
def get_collection_infos(collection_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        user_session = db.session
        user = user_session.query(User).filter_by(
            name=session['user']['name']).first()

        if not user:
            user_session.close()
            return jsonify({'error': 'User not found'}), 404

        collection = user_session.query(Collection).filter_by(
            id=collection_id,
            user_id=user.id
        ).first()
        if not collection:
            user_session.close()
            return jsonify({'error': 'Collection not found'}), 404

        print(collection)
        return jsonify({'name': collection.name, 'pic_url': collection.pic_url, 'description': collection.description})

    except Exception as e:
        print(f"Error fetching collection: {e}")
        return jsonify({'error': 'Failed to fetch collection'}), 500


@bp.route('/collection_tracks/<int:collection_id>', methods=['GET'])
def get_collection_tracks(collection_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        user_session = db.session
        user = user_session.query(User).filter_by(
            name=session['user']['name']).first()

        if not user:
            user_session.close()
            return jsonify({'error': 'User not found'}), 404

        collection = user_session.query(Collection).filter_by(
            id=collection_id,
            user_id=user.id
        ).first()
        if not collection:
            user_session.close()
            return jsonify({'error': 'Collection not found'}), 404
        sql = f"SELECT t.* FROM gpx_tracks t JOIN collection_track ct ON ct.track_id = t.id WHERE ct.collection_id = {collection_id}"
        gdf_tracks = gpd.GeoDataFrame.from_postgis(
            sql, con=user_session.connection(), geom_col='geom')
        if gdf_tracks.empty:
            return gdf_tracks.to_json()

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
        except Exception as e:
            print(f"Error formatting start_time or end_time: {e}")
        gdf_tracks['type'] = gdf_tracks['type'].fillna('other')
        gdf_tracks['link'] = gdf_tracks['link'].fillna('')
        gdf_tracks['comment'] = gdf_tracks['comment'].str.replace(
            '\\r\\n', '<br>', regex=False)

        user_session.commit()
        user_session.close()
        return gdf_tracks.to_json(), 200

    except Exception as e:
        print(f"Error fetching collection: {e}")
        return jsonify({'error': 'Failed to fetch collection'}), 500


@bp.route('/collections/<int:collection_id>', methods=['DELETE'])
def delete_collection(collection_id):
    """Delete a collection for the current user"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        user_session = db.session
        user = user_session.query(User).filter_by(
            name=session['user']['name']).first()

        if not user:
            user_session.close()
            return jsonify({'error': 'User not found'}), 404

        collection = user_session.query(Collection).filter_by(
            id=collection_id,
            user_id=user.id
        ).first()

        if not collection:
            user_session.close()
            return jsonify({'error': 'Collection not found'}), 404

        user_session.delete(collection)
        user_session.commit()

        user_session.close()
        return jsonify({'message': 'Collection deleted successfully'}), 200

    except Exception as e:
        print(f"Error deleting collection: {e}")
        return jsonify({'error': 'Failed to delete collection'}), 500


@bp.route('/collections/<int:collection_id>/tracks', methods=['POST'])
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

        track = db.session.query(GPXTrack).filter_by(id=int(track_id)).first()
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


@bp.route('/collections/<int:collection_id>/tracks/<int:track_id>', methods=['DELETE'])
def remove_track_from_collection(collection_id, track_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

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
            return jsonify({'error': 'Trail not in collection'}), 404

        collection.tracks.remove(track)
        db.session.commit()

        return jsonify({'message': 'Trail removed from collection successfully'}), 200
    except Exception as e:
        print(f"Error removing track from collection: {e}")
        print(traceback.format_exc())
        return jsonify({'error': 'Failed to remove trail from collection'}), 500


@bp.route('/tracks/<int:track_id>', methods=['PUT'])
def update_track(track_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    if not data or ('name' not in data and 'comment' not in data):
        return jsonify({'error': 'Name or comment is required'}), 400

    current_user = db.session.query(User).filter_by(
        uuid=session['user'].get('sub')).first()
    if not current_user:
        return jsonify({'error': 'User not found'}), 404

    track = db.session.query(GPXTrack).filter_by(id=track_id).first()
    if not track:
        return jsonify({'error': 'Track not found'}), 404

    if track.owner != current_user.uuid:
        return jsonify({'error': 'Forbidden'}), 403

    if 'name' in data:
        track.name = data['name']
    if 'comment' in data:
        track.comment = data['comment']

    db.session.commit()
    return jsonify({'message': 'Track updated successfully'}), 200


@bp.route('/tracks/<int:track_id>', methods=['DELETE'])
def delete_track(track_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    current_user = db.session.query(User).filter_by(
        uuid=session['user'].get('sub')).first()
    if not current_user:
        return jsonify({'error': 'User not found'}), 404

    track = db.session.query(GPXTrack).filter_by(id=track_id).first()
    if not track:
        return jsonify({'error': 'Track not found'}), 404

    if track.owner != current_user.uuid:
        return jsonify({'error': 'Forbidden'}), 403

    try:
        track.collections = []
        db.session.delete(track)
        db.session.commit()
        return jsonify({'message': 'Track deleted successfully'}), 200
    except Exception as e:
        print(f"Error deleting track: {e}")
        print(traceback.format_exc())
        return jsonify({'error': 'Failed to delete track'}), 500


@bp.route('/travel-wishes', methods=['POST'])
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


@bp.route('/travel-wishes/<int:wish_id>', methods=['GET'])
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


@bp.route('/travel-wishes/<int:wish_id>', methods=['PUT'])
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


@bp.route('/travel-wishes/<int:wish_id>', methods=['DELETE'])
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


@bp.route('/waypoints', methods=['GET'])
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
        return jsonify({'error': 'Failed to get the waypoints'}), 500


@bp.route('/waypoints', methods=['POST'])
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


@bp.route('/waypoints/<int:waypoint_id>', methods=['GET'])
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


@bp.route('/waypoints/<int:waypoint_id>', methods=['PUT'])
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


@bp.route('/waypoints/<int:waypoint_id>', methods=['DELETE'])
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


@bp.route('/waypoints/<int:waypoint_id>/add-to-collection/<int:collection_id>', methods=['POST'])
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
