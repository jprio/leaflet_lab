from requests.structures import CaseInsensitiveDict
import requests
import os
from dotenv import load_dotenv

load_dotenv()
geoapify_api_key = os.getenv('GEOAPIFY_API_KEY')


def basic_test():
    url = f"https://api.geoapify.com/v2/places?categories=commercial.supermarket&filter=rect%3A10.716463143326969%2C48.755151258420966%2C10.835314015356737%2C48.680903341613316&limit=20&apiKey={geoapify_api_key}"

    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json"

    resp = requests.get(url, headers=headers)

    # print(resp.status_code)
    # print(resp.json())
    for place in resp.json().get("features", []):
        print(place["properties"]["name"])


basic_test()
