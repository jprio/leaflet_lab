import os
import requests
from flask import Blueprint, request, session, jsonify
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import Point
from app.models.domain import db
from app.models.domain import User, Waypoint

bp = Blueprint('waypoints', __name__)


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
