import httpx
import json
import os
from datetime import date
from dotenv import load_dotenv
from pprint import pprint


COLLECTIONS = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/collections?level=2&format=json&apikey="
BIBS_PARAMS = "/bibs?level=2&format=json&apikey="
bibs_url = []

load_dotenv()
today = str(date.today())
os.makedirs("data/" + today, exist_ok=True)

with open("data/" + today + "/collections.json", "w") as f:
    response = httpx.get(COLLECTIONS + os.getenv("APIKEY"))
    data = response.json()
    collections = json.dumps(data)
    f.write(collections)

def bibs(collections):
    for collection in collections["collection"]:
        if "collection" in collection:
            bibs(collection)
            bibs_url.append(collection["pid"]["link"] + BIBS_PARAMS + os.getenv("APIKEY"))
        else:
            bibs_url.append(collection["pid"]["link"] + BIBS_PARAMS + os.getenv("APIKEY"))

bibs(data)
