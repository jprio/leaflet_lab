import gpxpy
import gpxpy.gpx
import pandas as pd
import sys
import os
sys.path.append(os.path.join('..', 'src'))
from app.utils.gpxutils import calculate_elevation_gain

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
    print(f"Track: {track.name}, 2D Distance: {distance_2d:.2f} meters")
    # elevation gain
    link=gpx.link
    print(f"Track: {track.name}, Link : {link}")
    duration = track.get_duration()
    print(f"Track: {track.name}, Duration: {duration} seconds")
    file_start_time, file_end_time = gpx.get_time_bounds()
    print(f"Track: {track.name}, Start Time: {file_start_time}, End Time: {file_end_time}")

    for segment in track.segments:
        point= segment.points[0]
        print ('Start at ({0},{1}) -> {2}'.format(point.latitude, point.longitude, point.elevation))

for waypoint in gpx.waypoints:
    print ('waypoint {0} -> ({1},{2})'.format(waypoint.name, waypoint.latitude, waypoint.longitude))

for route in gpx.routes:
    print ('Route:')

elevation_gain, elevation_loss = calculate_elevation_gain(gpx)   
print("elevation gain : {0:.2f} meters".format(float(elevation_gain)))
print("elevation loss : {0:.2f} meters".format(float(elevation_loss)))
print("elevation gain type : " + str(type(elevation_gain)))