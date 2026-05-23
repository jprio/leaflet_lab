import googlemaps
from datetime import datetime
import geocoder
import os
from dotenv import load_dotenv
import json
load_dotenv()
google_api_key = os.getenv('GOOGLE_API_KEY')


def test_google_api():
    gmaps = googlemaps.Client(key=google_api_key)
    # Geocoding an address
    # geocode_result = gmaps.geocode('1600 Amphitheatre Parkway, Mountain View, CA')
    # Look up an address with reverse geocoding
    reverse_geocode_result = gmaps.reverse_geocode((40.714224, -73.961452))
    # print(geocode_result[0]['address_components'])
    print(reverse_geocode_result[0]['address_components'][''])


def test_geocoder():
    # g = geocoder.google([41.539343, 75.104880], method='reverse', key=google_api_key)
    g = geocoder.google([42.154665, 77.352132],
                        method='reverse', key=google_api_key)
    print(g.json)
    print(g.city)
    print(g.state)
    print(g.state_long)
    print(g.country)

    print(g.country_long)
    print(g.county)
    print(g.country_long + ">" + g.state_long + ">" + g.county + ">" + g.city)
    address_dict = {'country': g.country_long,
                    'state': g.state_long, 'county': g.county, 'city': g.city}
    print(json.dumps(address_dict, indent=4))


def test_gmaps_places():
    gmaps = googlemaps.Client(key=google_api_key)
    # Search for places nearby a location
    # places_result = gmaps.places_nearby(location=(42.154665, 77.352132), radius=500, type='restaurant')
    places_result = gmaps.places_nearby(
        location=(42.154665, 77.352132), radius=500, type="point_of_interest")
    for place in places_result['results']:
        print(place['types'])
        print(place['name'])


def find_city():
    gmaps = googlemaps.Client(key=google_api_key)
    results = gmaps.places(query="Antony", type="city")
    for place in results['results']:
        print(place['name'])


def test_textsearch():
    import requests

    api_key = key = google_api_key
    query = "Bichkek"

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": query,
        "key": api_key,
        "language": "fr"  # Optionnel : spécifie la langue des résultats
    }

    response = requests.get(url, params=params)
    data = response.json()
    print(data)
    # Extraction des noms et adresses
    if data["status"] == "OK":
        for place in data["results"]:
            print(f"Nom: {place['name']}")
            print(f"Adresse: {place.get('formatted_address', 'N/A')}")
            print("-" * 20)


# test_geocoder()
# test_google_api()
# test_gmaps_places()
# find_city()
test_textsearch()
