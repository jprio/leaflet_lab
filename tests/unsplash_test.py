import requests
import unittest
api_key = 'Y1Ri-AxBBUpySRvlADwGX-CTWCY9yZv0mJ3peT2_2VE'


class TestUnsplashAPI(unittest.TestCase):
    def test_unsplash_api(self):
        response = requests.get(
            "https://api.unsplash.com/photos/random/?query=indonesie&client_id=Y1Ri-AxBBUpySRvlADwGX-CTWCY9yZv0mJ3peT2_2VE").json()

        print(response["urls"]["small_s3"])
