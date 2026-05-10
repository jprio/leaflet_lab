import requests
api_key = 'Y1Ri-AxBBUpySRvlADwGX-CTWCY9yZv0mJ3peT2_2VE'

response = requests.get(
    "https://api.unsplash.com/photos/random/?query=indonesie&client_id=Y1Ri-AxBBUpySRvlADwGX-CTWCY9yZv0mJ3peT2_2VE").json()

print(response["urls"]["small_s3"])
