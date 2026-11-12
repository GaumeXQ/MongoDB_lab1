"""
Small functions used by the step scripts: insert documents, create indexes,
run a query and read the main numbers of explain().
"""
import time

from pymongo import MongoClient

from config import MONGO_URI, PARAMS, TIME_LIMIT_MS


def connect():
    return MongoClient(MONGO_URI)


def insert_in_batches(db, documents, batch_size=5000):
    """Insert (collection, document) pairs, 5,000 at a time (much faster than
    inserting them one by one)."""
    batches = {}
    for collection, document in documents:
        batch = batches.setdefault(collection, [])
        batch.append(document)
        if len(batch) == batch_size:
            db[collection].insert_many(batch)
            batch.clear()
    for collection, batch in batches.items():
        if batch:
            db[collection].insert_many(batch)


def create_indexes(db, model):
    for collection, indexes in model.INDEXES.items():
        for keys in indexes:
            db[collection].create_index(keys)


def drop_indexes(db):
    """Drop every index except _id, which MongoDB does not allow to drop."""
    for collection in db.list_collection_names():
        db[collection].drop_indexes()


def pipeline_of(model, query):
    """(collection, pipeline) of a query in a model, with the parameters."""
    return getattr(model, query)(PARAMS[query])


def run(db, collection, pipeline):
    """Run a pipeline. Returns (result documents, milliseconds)."""
    start = time.perf_counter()
    result = list(db[collection].aggregate(pipeline, allowDiskUse=True,
                                           maxTimeMS=TIME_LIMIT_MS))
    return result, (time.perf_counter() - start) * 1000


def explain(db, collection, pipeline, hint=None):
    """Main numbers of explain(): documents read, index keys read, and whether
    an index was used. The numbers of the $lookup stages are added too.
    `hint` forces an index (its name) or a full scan ({"$natural": 1})."""
    command = {"aggregate": collection, "pipeline": pipeline, "cursor": {},
               "allowDiskUse": True}
    if hint:
        command["hint"] = hint
    plan = db.command("explain", command, verbosity="executionStats")
    return {"docs_examined": total(plan, "totalDocsExamined"),
            "keys_examined": total(plan, "totalKeysExamined"),
            "uses_index": "IXSCAN" in str(plan)}


def total(node, key):
    """Add up every value of `key` anywhere inside the explain output."""
    if isinstance(node, dict):
        return sum(value if name == key and isinstance(value, int) else total(value, key)
                   for name, value in node.items())
    if isinstance(node, list):
        return sum(total(value, key) for value in node)
    return 0
