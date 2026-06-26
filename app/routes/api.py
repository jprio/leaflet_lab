from flask import Blueprint
from .collections import bp as collections_bp
from .tracks import bp as tracks_bp
from .travel_wishes import bp as travel_wishes_bp
from .waypoints import bp as waypoints_bp

bp = Blueprint('api', __name__, url_prefix='/api')

bp.register_blueprint(collections_bp)
bp.register_blueprint(tracks_bp)
bp.register_blueprint(travel_wishes_bp)
bp.register_blueprint(waypoints_bp)
