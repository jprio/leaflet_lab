from datetime import datetime
import os
from sqlalchemy import text
from typing import List
from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy import Table, Column, Integer, String, MetaData, Sequence, Identity, DateTime, Date, BigInteger
from geoalchemy2 import Geometry, WKTElement
from shapely.geometry import LineString
from sqlalchemy import event, func
from sqlalchemy.orm import attributes
from geoalchemy2.shape import to_shape
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSON
from dataclasses import dataclass, asdict
from flask_sqlalchemy import SQLAlchemy


class Base(DeclarativeBase):
    pass

    def __int__(self):
        pass


db = SQLAlchemy(model_class=Base)


@dataclass
class User(Base):
    __tablename__ = "user_account"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True)

    # id = Column(Integer, Identity(start=1), primary_key=True)
    name: Mapped[str] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(50), unique=True)
    collections: Mapped[List["Collection"]] = relationship("Collection",
                                                           back_populates="user", cascade="all, delete-orphan"
                                                           )
    travel_wishes: Mapped[List["TravelWish"]] = relationship("TravelWish",
                                                             back_populates="user", cascade="all, delete-orphan"
                                                             )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, name={self.name!r}, email={self.email!r}, collections={self.collections!r})"


collection_track = Table(
    "collection_track",
    Base.metadata,
    Column("collection_id", ForeignKey("collection.id"), primary_key=True),
    Column("track_id", ForeignKey("gpx_tracks.id"), primary_key=True),
)


@dataclass
class Collection(Base):
    __tablename__ = "collection"
    # id: Mapped[int] = mapped_column(primary_key=True, )
    id = Column(Integer, Identity(start=1), primary_key=True)
    name: Mapped[str]
    description: Mapped[str]
    pic_url: Mapped[Optional[str]]
    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"))
    user: Mapped["User"] = relationship("User", back_populates="collections")
    tracks: Mapped[List["GPXTrack"]] = relationship(
        "GPXTrack",
        secondary=collection_track,
        back_populates="collections"
    )

    def __repr__(self) -> str:
        return f"Collection(id={self.id!r}, name={self.name!r})"


class GPXTrack(Base):
    __tablename__ = 'gpx_tracks'
    __allow_unmapped__ = True
    id = Column(BigInteger, primary_key=True)
    elevation_gain = Column(Integer)
    elevation_loss = Column(Integer)
    length = Column(Integer)
    name = Column(String)
    type = Column(String)
    comment = Column(String)
    start_point_geo = Column(JSON, nullable=False, default=dict)
    link = Column(String)
    owner = Column(String, nullable=False)
    geom = Column(Geometry(geometry_type='LINESTRING', srid=4326))
    insert_date: Column[datetime] = Column(
        DateTime, server_default=func.now(), onupdate=func.now())
    start_time: Column[datetime] = Column(DateTime)
    end_time: Column[datetime] = Column(DateTime)
    collections: Mapped[List["Collection"]] = relationship(
        "Collection",
        secondary=collection_track,
        back_populates="tracks"
    )

    # length: int
    def __repr__(self) -> str:
        return f"GPXTrack(id={self.id!r}, name={self.name!r})"


class TravelWish(Base):
    __tablename__ = 'travel_wishes'
    id = Column(Integer, Identity(start=1), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    region: Mapped[Optional[str]] = mapped_column(String(255))
    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"))
    user: Mapped["User"] = relationship("User", back_populates="travel_wishes")
    created_at: Column[datetime] = Column(DateTime, server_default=func.now())
    updated_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"TravelWish(id={self.id!r}, title={self.title!r}, region={self.region!r})"

# @event.listens_for(GPXTrack, 'before_commit')
# def gpxtrack_before_commit(session, instance):
#     print(instance)


@event.listens_for(GPXTrack, "before_insert")
def receive_before_insert(mapper, connection, target):
    print("Before inserting GPXTrack:", target)


@event.listens_for(GPXTrack, "load")
def load_b(track, context):
    print("Loading GPXTrack instance with id:", track.id)
    shapely_point = to_shape(track.geom)
    track.length = shapely_point.length * 100
    # if "length" in track.__dict__:
    #     attributes.set_committed_value(track, track.length, 12)

    print(track)
