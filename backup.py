import httpx
import json
import os
from datetime import date
from dotenv import load_dotenv
from pprint import pprint


COLLECTIONS = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/collections?level=2&format=json&apikey="
BIBS1 = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/collections/"
BIBS2 = "/bibs?level=2&format=json&apikey="

load_dotenv()
today = str(date.today())
os.makedirs("data/" + today, exist_ok=True)

with open("data/" + today + "/collections.json", "w") as f:
    response = httpx.get(COLLECTIONS + os.getenv("APIKEY"))
    collections = json.dumps(response.json())
    f.write(collections)

for collection in collections:
    pass
