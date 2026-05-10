from flask_sqlalchemy import SQLAlchemy
from app.models.domain import Base, User, Collection, Trail, Track

db = SQLAlchemy(model_class=Base)
