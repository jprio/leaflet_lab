from flask import Blueprint, request, session, jsonify
from app.models.domain import db
from app.models.domain import User, TravelWish

bp = Blueprint('travel_wishes', __name__)


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
