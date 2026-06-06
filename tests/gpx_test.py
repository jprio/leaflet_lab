from contextlib import redirect_stdout
import unittest

from geoalchemy2 import WKTElement
from app.models import persistence
from app.models.domain import GPXTrack
from app.utils.gpxutils import calculate_elevation_gain
import gpxpy
import gpxpy.gpx
import pandas as pd
import sys
import os
sys.path.append(os.path.join('..', 'src'))


class TestGpxParsing(unittest.TestCase):
    @unittest.skip("Test de parsing GPX avec gpxpy")
    def test_gpxpy(self):
        # gpx_file = open('tests/gpx/kol-suu-naryn-kyrgyzstan.gpx', 'r')
        # gpx_file = open('tests/gpx/kolsu-naryn.gpx', 'r')
        gpx_file = open('tests/gpx/red-hills-canyon.gpx', 'r')

        gpx = gpxpy.parse(gpx_file)
        for track in gpx.tracks:
            print(track.name)
            # Calculate 3D distance in meters
            distance_3d = track.length_3d()
            print(f"Track: {track.name}, Distance: {distance_3d:.2f} meters")

            # Calculate 2D distance
            distance_2d = track.length_2d()
            print(
                f"Track: {track.name}, 2D Distance: {distance_2d:.2f} meters")
            # elevation gain
            link = gpx.link
            print(f"Track: {track.name}, Link : {link}")
            duration = track.get_duration()
            print(f"Track: {track.name}, Duration: {duration} seconds")
            file_start_time, file_end_time = gpx.get_time_bounds()
            print(
                f"Track: {track.name}, Start Time: {file_start_time}, End Time: {file_end_time}")

            for segment in track.segments:
                point = segment.points[0]
                print('Start at ({0},{1}) -> {2}'.format(point.latitude,
                                                         point.longitude, point.elevation))

        for waypoint in gpx.waypoints:
            print('waypoint {0} -> ({1},{2})'.format(waypoint.name,
                                                     waypoint.latitude, waypoint.longitude))

        for route in gpx.routes:
            print('Route:')

        elevation_gain, elevation_loss = calculate_elevation_gain(gpx)
        print("elevation gain : {0:.2f} meters".format(float(elevation_gain)))
        print("elevation loss : {0:.2f} meters".format(float(elevation_loss)))
        print("elevation gain type : " + str(type(elevation_gain)))

    # @unittest.skip("Test de parsing GPX avec geopandas")
    def test_geopandas(self):
        import geopandas as gpd
        # Ou lecture de la couche 'tracks' pour l'itinéraire global
        gdf_wp = gpd.read_file(
            'tests/gpx/Boucle Red Rocks.gpx', layer='waypoints')
        print(gdf_wp.head())
        gdf_tracks = gpd.read_file(
            'tests/gpx/Boucle Red Rocks.gpx', layer='tracks')
        gdf_tracks = gdf_tracks.to_crs(gdf_wp.crs)

        print(gdf_tracks.head())
        joined = gpd.sjoin(gdf_wp, gdf_tracks, how="right",
                           predicate="intersects")

        print(joined.head())
        print(joined.columns)
        print(joined['name_left'])
        print(joined['geometry'])

    def test_gpx_read_gpx(self):
        from gpx import read_gpx
        from sqlalchemy.orm import sessionmaker
        from datetime import datetime
        # gpx_file = open('tests/gpx/Boucle Red Rocks.gpx', 'r')
        gpx_data = read_gpx("tests/gpx/Boucle Red Rocks.gpx")
        engine = persistence.get_engine()

        Session = sessionmaker(bind=engine)
        print(gpx_data.trk[0].name)
        print(gpx_data.metadata)
        print(gpx_data.metadata.name)
        print(gpx_data.metadata.author.link.href)
        sess = Session()
        try:
            new_track = GPXTrack(name=gpx_data.trk[0].name, geom=WKTElement(gpx_data.to_wkt(), srid=4326), owner="ME", type="HIKE", elevation_gain=0, elevation_loss=0,
                                 link=gpx_data.metadata.author.link.href, start_time=datetime.now(), end_time=datetime.now(), insert_date=datetime.now().isoformat(timespec='seconds'), length=0, comment="comment", start_point_geo={})
            sess.add(new_track)
            sess.commit()
            sess.close()
        except Exception as e:
            print(f"Error inserting track, Error: {e}")
            sess.rollback()
            sess.close()


if __name__ == '__main__':
    unittest.main()
