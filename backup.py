import httpx
import json
import os
from datetime import date
from dotenv import load_dotenv
from pprint import pprint


COLLECTIONS = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/collections?level=2&format=json&apikey="
BIBS_PARAMS = "/bibs?level=2&format=json&limit=100&apikey="
TODAY = str(date.today())


load_dotenv()


def bibs(collections):
    """Recursively search collections and create urls"""
    for collection in collections["collection"]:
        if "collection" in collection:
            bibs(collection)

        counter = 0
        json_output = []

        paginate(collection, counter, json_output)

        with open("data/" + TODAY + "/" + collection["name"] + ".json", "w") as f2:
            bibs_json = json.dumps(json_output)
            f2.write(bibs_json)


def paginate(collection, counter, json_output):
    """Paginate through results"""
    if "pid" in collection:
        url = (
            collection["pid"]["link"]
            + BIBS_PARAMS
            + os.getenv("APIKEY")
            + "&offset="
            + str(counter)
        )

        response = httpx.get(url, timeout=30)
        data = response.json()
        json_output.append(data)
        counter += 100

        if "bib" in data:
            pprint(data["total_record_count"])
            pprint(counter)
            pprint("-------")
            paginate(collection, counter, json_output)
        else:
            return json_output


def main():
    """run the program"""

    # see if data for today already exists
    try:
        os.makedirs("data/" + TODAY, exist_ok=False)
    except FileExistsError:
        print("Data for today already exists")
        return

    # get collections data
    with open("data/" + TODAY + "/collections.json", "w") as f1:
        response = httpx.get(COLLECTIONS + os.getenv("APIKEY"), timeout=30)
        data = response.json()
        collections = json.dumps(data)
        f1.write(collections)

    # create urls for bibs data, save as tuples along with name
    bibs(data)


main()
