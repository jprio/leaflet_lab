import requests
import pandas as pd
from dotenv import load_dotenv
import os
import unittest

lat = 42.87
lon = 44.59
load_dotenv()  # Charger les variables d'environnement à partir du fichier .env
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")


class TestOpenWeatherMapAPI(unittest.TestCase):
    def test_openweathermap_api(self):
        print(f"Using OpenWeatherMap API key: {OPENWEATHERMAP_API_KEY}")
        # response = requests.get(
        #     "https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHERMAP_API_KEY}&lang=fr")

        response = requests.get(
            "http://api.openweathermap.org/data/2.5/forecast?id=524901&appid={OPENWEATHERMAP_API_KEY}")
        print(response.json())
