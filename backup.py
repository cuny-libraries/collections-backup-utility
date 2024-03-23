import dotenv
import httpx
import json
import os
from datetime import date
from pprint import pprint


COLLECTIONS_JSON = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/collections?level=20&format=json&apikey="
COLLECTIONS_XML = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/collections?level=20&apikey="
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
            coll_id = collection["mms_id"]["value"]
            global mmsids

            with open(
                "data/" + TODAY + "/" + college + "/" + coll_name + "-" + coll_id + ".csv", "w"
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

    if date.today().day == 1:
        # see if data for today already exists
        for college, key in config.items():
            print("working on " + college + " collections...")
            try:
                os.makedirs("data/" + TODAY + "/" + college, exist_ok=False)
            except FileExistsError:
                print("Data for today already exists")
                return

            # get collections data in XML; write to file
            with open("data/" + TODAY + "/" + college + "/COLLECTIONS.xml", "w") as f1:
                response1 = httpx.get(COLLECTIONS_XML + key, timeout=500)
                data_xml = response1.text
                f1.write(data_xml)

            # get collections data in JSON; run collection-level analyis
            response2 = httpx.get(COLLECTIONS_JSON + key, timeout=500)
            data_json = response2.json()
            bibs(data_json, key, college)
    else:
        print("Not the first of the month. No action taken.")


if __name__ == "__main__":
    main()
