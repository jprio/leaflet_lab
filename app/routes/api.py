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
from app.models.domain import User, Collection, GPXTrack
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


@bp.route('/collections', methods=['POST'])
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
        print(f"pic url : {pic_url} for {data['name']}")
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


@bp.route('/collections/info/<int:collection_id>', methods=['GET'])
def get_collection_infos(collection_id):
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
        gdf_tracks['comment'].str.replace('\r\n', '<br>')

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
