import traceback
from flask import Blueprint, request, session, jsonify
import geopandas as gpd
from sqlalchemy import text
from app.models.domain import db
from app.models.domain import User, GPXTrack

bp = Blueprint('tracks', __name__)


@bp.route('/find_tracks')
def find_tracks():
    NW_lat = request.args.get('NW_lat')
    NW_lon = request.args.get('NW_lon')
    SE_lat = request.args.get('SE_lat')
    SE_lon = request.args.get('SE_lon')
    category = request.args.get('category')

    sql = text("""
    SELECT *
    FROM gpx_tracks
    WHERE ST_X(ST_StartPoint(geom)) BETWEEN :NW_lon AND :SE_lon
    AND ST_Y(ST_StartPoint(geom)) BETWEEN :SE_lat AND :NW_lat
    """)
    gdf_tracks = gpd.GeoDataFrame.from_postgis(
        sql,
        con=db.session.connection(),
        params={
            "NW_lon": float(NW_lon) if NW_lon is not None else 0.0,
            "SE_lon": float(SE_lon) if SE_lon is not None else 0.0,
            "SE_lat": float(SE_lat) if SE_lat is not None else 0.0,
            "NW_lat": float(NW_lat) if NW_lat is not None else 0.0
        }
    )
    print(10*"=")
    print(gdf_tracks)
    print(10*"=")
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
    current_user_uuid = session.get('user', {}).get(
        'sub') if 'user' in session else None
    gdf_tracks['is_owner'] = gdf_tracks['owner'].fillna(
        '').eq(current_user_uuid)
    return gdf_tracks.to_json()


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
    if 'type' in data:
        track.type = data['type']
    if 'link' in data:
        track.link = data['link']

    db.session.commit()
    return jsonify({'message': 'Track updated successfully'}), 200


@bp.route('/tracks/<int:track_id>', methods=['GET'])
def get_track(track_id):
    print(f"Fetching track with id: {track_id}")
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    sql = text("""
        SELECT *
        FROM gpx_tracks
        WHERE id=:track_id
        """)
    gdf_tracks = gpd.GeoDataFrame.from_postgis(
        sql,
        con=db.session.connection(),
        params={"track_id": track_id}
    )
    if gdf_tracks.empty:
        return jsonify({'error': 'Track not found'}), 404
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

    return gdf_tracks.to_json(), 200


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
