import dotenv
import httpx
import json
import os
from datetime import date
from pprint import pprint


COLLECTIONS = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/collections?level=20&format=json&apikey="
BIBS_PARAMS = "/bibs?level=2&format=json&limit=100&apikey="
TODAY = str(date.today())
mmsids = []

config = dotenv.dotenv_values(".env")


def bibs(collections, key, college):
    """Recursively search collections"""
    try:
        for collection in collections["collection"]:
            if "collection" in collection:
                bibs(collection, key, college)

            counter = 0
            paginate(collection, counter, key)

            # remove "/"s from collection names so they don't break paths
            coll_name = collection["name"].replace("/", ".")
            global mmsids

            with open(
                "data/" + TODAY + "/" + college + "/" + coll_name + ".csv", "w"
            ) as f2:
                f2.write("MMS ID\n")
                for mmsid in mmsids:
                    f2.write(mmsid + "\n")
            mmsids = []
    except KeyError:
        print("No collections found.")
        return


def paginate(collection, counter, key):
    """Paginate through results"""
    if "pid" in collection:
        url = collection["pid"]["link"] + BIBS_PARAMS + key + "&offset=" + str(counter)

        response = httpx.get(url, timeout=500)
        data = response.json()
        counter += 100
        global mmsids

        if "bib" in data:
            for bib in data["bib"]:
                mmsids.append(bib["mms_id"])
            paginate(collection, counter, key)
        else:
            return


def main():
    """run the program"""

    # see if data for today already exists
    for college, key in config.items():
        print("working on " + college + " collections...")
        try:
            os.makedirs("data/" + TODAY + "/" + college, exist_ok=False)
        except FileExistsError:
            print("Data for today already exists")
            return

        # get collections data
        with open("data/" + TODAY + "/" + college + "/COLLECTIONS.json", "w") as f1:
            response = httpx.get(COLLECTIONS + key, timeout=500)
            data = response.json()
            collections = json.dumps(data)
            f1.write(collections)

        bibs(data, key, college)


main()
