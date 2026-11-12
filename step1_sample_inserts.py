"""
Step 1 - Insert sample documents of each model.

The example documents are in examples/<model>.json, one file per model, in
MongoDB's JSON format ({"$date": ...} for dates). They are real documents of
the SF 0.2 dataset: order 1, its first line item, and the part and supplier
of that line.

    python step1_sample_inserts.py

Creates the databases m0_examples, m1_examples, m2_examples and p_examples
and prints each document back from MongoDB.
"""
from bson import json_util

from helpers import connect
from models import MODELS

client = connect()

for model_id, model in MODELS.items():
    with open(f"examples/{model_id}.json", encoding="utf-8") as file:
        examples = json_util.loads(file.read())    # {collection: [documents]}

    db = client[f"{model_id}_examples"]
    client.drop_database(db.name)
    print(f"\n===== {model.NAME}  (database {db.name})")

    for collection, documents in examples.items():
        for document in documents:
            db[collection].insert_one(document)
            stored = db[collection].find_one({"_id": document["_id"]})
            print(f"\ndb.{collection}:")
            print(json_util.dumps(stored, indent=2))
