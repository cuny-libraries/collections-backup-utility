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


def bibs(collections):
    for collection in collections["collection"]:
        if "collection" in collection:
            bibs(collection)
        bibs_url.append(collection["pid"]["link"] + BIBS_PARAMS + os.getenv("APIKEY"))


def main():
    try:
        os.makedirs("data/" + today, exist_ok=False)
    except FileExistsError:
        print("Data for today already exists")
        return

    with open("data/" + today + "/collections.json", "w") as f1:
        response = httpx.get(COLLECTIONS + os.getenv("APIKEY"))
        data = response.json()
        collections = json.dumps(data)
        f1.write(collections)

    bibs(data)

    for index, url in enumerate(bibs_url):
        with open("data/" + today + "/bibs" + str(index) + ".json", "w") as f2:
            response = httpx.get(url)
            data = response.json()
            bib = json.dumps(data)
            f2.write(bib)

main()
