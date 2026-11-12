"""
Step 5 - Extra experiments used in the report (run after step 4).

    python step5_extra_experiments.py --name sf02

1. Is an index useful for Q1?  Q1 in M2 with and without an index on
   shipdate, for the default date (98.6 % of the lines) and a selective one.
2. M1, Q3: what changes if the index does not include lines.shipdate.
3. Storage of each model (data, disk and index size).
4. Cost of writes: updating one supplier and inserting one order with 4
   lines. Every change is undone afterwards, so the data stays as loaded.

The results are saved in results/extra_<name>.json.
"""
import argparse
import json
import statistics
import time
from datetime import datetime

from config import PARAMS, database_name
from helpers import connect, explain
from models import MODELS, m1_order_rooted, m2_line_rooted, p_proposed
from models.common import flat_line, line_id

parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True, help="dataset loaded in step 2")
args = parser.parse_args()
client = connect()
dbs = {model_id: client[database_name(model_id, args.name)] for model_id in MODELS}
results = {}


def median_ms(db, collection, pipeline, hint, repetitions=3):
    """Median time forcing a plan: an index name, or {"$natural": 1} for a full scan."""
    times = []
    for _ in range(repetitions + 1):          # the first run is a warm-up
        start = time.perf_counter()
        list(db[collection].aggregate(pipeline, hint=hint, allowDiskUse=True))
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times[1:])


# ---------------------------------------------------- 1. index for Q1 (M2) --
db = dbs["m2"]
index = db.lineitem.create_index("shipdate")
total_lines = db.lineitem.estimated_document_count()
for label, day in (("default date", PARAMS["q1"]["date"]),
                   ("selective date", datetime(1992, 3, 1))):
    collection, pipeline = m2_line_rooted.q1({"date": day})
    percent = 100 * db.lineitem.count_documents({"shipdate": {"$lte": day}}) / total_lines
    scan_ms = median_ms(db, collection, pipeline, {"$natural": 1})
    index_ms = median_ms(db, collection, pipeline, index)
    results[f"q1 {label}"] = {"percent_of_lines": round(percent, 2),
                              "full_scan_ms": scan_ms, "index_ms": index_ms}
    print(f"1. Q1, {label} ({percent:.1f} % of lines): "
          f"full scan {scan_ms:,.0f} ms, with index {index_ms:,.0f} ms")
db.lineitem.drop_index(index)

# ------------------------------------------- 2. M1, Q3 with a shorter index --
db = dbs["m1"]
collection, pipeline = m1_order_rooted.q3(PARAMS["q3"])
full_index = "mktsegment_1_orderdate_1_lines.shipdate_1"      # created in step 2
short_index = db.orders.create_index([("mktsegment", 1), ("orderdate", 1)])
for label, index in (("index with lines.shipdate", full_index),
                     ("index without lines.shipdate", short_index)):
    ms = median_ms(db, collection, pipeline, index)
    read = explain(db, collection, pipeline, index)["docs_examined"]
    results[f"m1 q3 {label}"] = {"ms": ms, "docs_examined": read}
    print(f"2. M1 Q3, {label}: {ms:,.0f} ms, {read:,} orders read")
db.orders.drop_index(short_index)

# ------------------------------------------------------------- 3. storage --
for model_id, db in dbs.items():
    data = disk = indexes = 0
    for collection in db.list_collection_names():
        stats = db.command("collStats", collection)
        data += stats["size"]
        disk += stats["storageSize"]
        indexes += stats["totalIndexSize"]
    results[f"storage {model_id}"] = {"data_mb": round(data / 1e6),
                                      "disk_mb": round(disk / 1e6),
                                      "index_mb": round(indexes / 1e6)}
    print(f"3. Storage {MODELS[model_id].NAME}: {results[f'storage {model_id}']}")

# --------------------------------------------------------- 4. write costs --
# a) Change the balance (acctbal) of supplier 1. Where is it stored?
#    M0: once, in db.supplier.   M1 and P: inside the parts that it supplies.
#    M2: in every partsupp document of that supplier.
original_balance = dbs["m0"].supplier.find_one({"_id": 1})["acctbal"]


def update_supplier(model_id, balance):
    """Set the balance of supplier 1; returns how many documents changed."""
    db = dbs[model_id]
    if model_id == "m0":
        result = db.supplier.update_one({"_id": 1}, {"$set": {"acctbal": balance}})
    elif model_id == "m2":
        result = db.partsupp.update_many({"suppkey": 1},
                                         {"$set": {"s_acctbal": balance}})
    else:   # m1 and p: the supplier is an element of the "suppliers" array
        result = db.parts.update_many(
            {"suppliers.suppkey": 1},
            {"$set": {"suppliers.$[s].acctbal": balance}},
            array_filters=[{"s.suppkey": 1}])
    return result.matched_count


# b) Insert a new order with 4 lines. How many documents does it take?
class TinyTPCH:
    """Just enough reference data to build the documents of the new order."""
    regions = {0: {"name": "EUROPE"}}
    nations = {0: {"name": "FRANCE", "regionkey": 0}}
    suppliers = {1: {"nationkey": 0}}
    customers = {1: {"nationkey": 0, "mktsegment": "BUILDING"}}


ORDER = {"orderkey": 999_999_999, "custkey": 1, "orderdate": datetime(1997, 1, 1),
         "shippriority": 0}
LINES = [{"orderkey": 999_999_999, "partkey": 1, "suppkey": 1, "linenumber": n,
          "quantity": 1.0, "extendedprice": 10.0, "discount": 0.0, "tax": 0.0,
          "returnflag": "N", "linestatus": "O", "shipdate": datetime(1997, 1, 2)}
         for n in range(1, 5)]


def new_order_documents(model_id):
    """(collection, document) pairs needed to store the new order."""
    if model_id == "m0":
        return ([("orders", {"_id": ORDER["orderkey"], "custkey": 1,
                             "orderdate": ORDER["orderdate"], "shippriority": 0})] +
                [("lineitem", {"_id": line_id(l["orderkey"], l["linenumber"]), **l})
                 for l in LINES])
    if model_id == "m1":
        return [("orders", m1_order_rooted.order_document(ORDER, LINES, TinyTPCH))]
    if model_id == "m2":
        return [("lineitem", flat_line(ORDER, l, TinyTPCH)) for l in LINES]
    return [("lineitem", p_proposed.line_document(ORDER, l, TinyTPCH)) for l in LINES]


for model_id, db in dbs.items():
    # An index on the supplier key, otherwise the update reads every document.
    if model_id == "m2":
        db.partsupp.create_index("suppkey")
    elif model_id in ("m1", "p"):
        db.parts.create_index("suppliers.suppkey")

    start = time.perf_counter()
    changed = update_supplier(model_id, 1234.5)
    update_ms = (time.perf_counter() - start) * 1000
    update_supplier(model_id, original_balance)           # undo
    if model_id == "m2":
        db.partsupp.drop_index("suppkey_1")
    elif model_id in ("m1", "p"):
        db.parts.drop_index("suppliers.suppkey_1")

    documents = new_order_documents(model_id)
    start = time.perf_counter()
    for collection, document in documents:
        db[collection].insert_one(document)
    insert_ms = (time.perf_counter() - start) * 1000
    for collection, document in documents:                 # undo
        db[collection].delete_one({"_id": document["_id"]})

    results[f"writes {model_id}"] = {
        "supplier_update_documents": changed, "supplier_update_ms": round(update_ms, 2),
        "insert_order_documents": len(documents), "insert_order_ms": round(insert_ms, 2)}
    print(f"4. Writes {MODELS[model_id].NAME}: {results[f'writes {model_id}']}")

with open(f"results/extra_{args.name}.json", "w") as file:
    json.dump(results, file, indent=1)
