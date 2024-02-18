import httpx
import json
import os
from datetime import date
from dotenv import load_dotenv
from pprint import pprint


COLLECTIONS = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/collections?level=2&format=json&apikey="
BIBS_PARAMS = "/bibs?level=2&format=json&limit=100&offset=5000&apikey="
bibs_url = []


load_dotenv()
today = str(date.today())


def bibs(collections):
    """ Recursively search collections and create urls """
    for collection in collections["collection"]:
        if "collection" in collection:
            bibs(collection)
        bibs_url.append(
            (
                collection["pid"]["link"] + BIBS_PARAMS + os.getenv("APIKEY"),
                collection["name"],
            )
        )


def main():
    """ run the program """

    # see if data for today already exists
    try:
        os.makedirs("data/" + today, exist_ok=False)
    except FileExistsError:
        print("Data for today already exists")
        return

    # get collections data
    with open("data/" + today + "/collections.json", "w") as f1:
        response = httpx.get(COLLECTIONS + os.getenv("APIKEY"))
        data = response.json()
        collections = json.dumps(data)
        f1.write(collections)

    # create urls for bibs data, save as tuples along with name
    bibs(data)

    # create bibs files; populate from API
    for index, url in enumerate(bibs_url):
        with open(
            "data/" + today + "/" + str(index) + " -- " + url[1] + ".json", "w"
        ) as f2:
            response = httpx.get(url[0])
            data = response.json()
            bibs_json = json.dumps(data)
            f2.write(bibs_json)


main()
