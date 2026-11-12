"""
M0 - Normalised (baseline).

One collection per TPC-H table, and every relationship is a reference that
the queries resolve with $lookup, like a JOIN in SQL. Example document of
each collection: examples/m0.json

    lineitem { _id, orderkey -> orders, partkey -> part, suppkey -> supplier, ... }
    orders   { _id, custkey -> customer, orderdate, shippriority }
    customer { _id, nationkey -> nation, mktsegment }
    ...
"""
from models.common import Q2_SORT, line_id, q1_group_and_sort, revenue

NAME = "M0 normalised"


# ---------------------------------------------------------------- documents --
def documents(tpch):
    """Yield (collection, document) for every document of the model."""
    for r in tpch.regions.values():
        yield "region", {"_id": r["regionkey"], "name": r["name"]}
    for n in tpch.nations.values():
        yield "nation", {"_id": n["nationkey"], "name": n["name"],
                         "regionkey": n["regionkey"]}
    for s in tpch.suppliers.values():
        yield "supplier", {"_id": s["suppkey"], "name": s["name"],
                           "address": s["address"], "nationkey": s["nationkey"],
                           "phone": s["phone"], "acctbal": s["acctbal"],
                           "comment": s["comment"]}
    for c in tpch.customers.values():
        yield "customer", {"_id": c["custkey"], "nationkey": c["nationkey"],
                           "mktsegment": c["mktsegment"]}
    for p in tpch.parts():
        yield "part", {"_id": p["partkey"], "mfgr": p["mfgr"], "type": p["type"],
                       "size": p["size"]}
    for ps in tpch.partsupps():
        yield "partsupp", {"_id": ps["partkey"] * 10_000_000 + ps["suppkey"],
                           "partkey": ps["partkey"], "suppkey": ps["suppkey"],
                           "supplycost": ps["supplycost"]}
    for o in tpch.orders():
        yield "orders", {"_id": o["orderkey"], "custkey": o["custkey"],
                         "orderdate": o["orderdate"],
                         "shippriority": o["shippriority"]}
    for l in tpch.lineitems():
        yield "lineitem", {"_id": line_id(l["orderkey"], l["linenumber"]), **l}


# ------------------------------------------------------------------ indexes --
# One index for each join key and each filter.
INDEXES = {
    "lineitem": [[("orderkey", 1), ("shipdate", 1)]],
    "orders": [[("custkey", 1), ("orderdate", 1)]],
    "customer": [[("nationkey", 1)], [("mktsegment", 1)]],
    "part": [[("size", 1), ("type", 1)]],
    "partsupp": [[("partkey", 1)]],
    "nation": [[("regionkey", 1)]],
}


# ------------------------------------------------------------------ queries --
def join(collection, local_field, foreign_field, name, filter_stages=None):
    """SQL JOIN: $lookup brings the matching documents in an array, and
    $unwind turns that array into one document per match.
    filter_stages (optional) filter the joined collection before joining."""
    lookup = {"from": collection, "localField": local_field,
              "foreignField": foreign_field, "as": name}
    if filter_stages:
        lookup["pipeline"] = filter_stages
    return [{"$lookup": lookup}, {"$unwind": "$" + name}]


def q1(p):
    return "lineitem", [
        {"$match": {"shipdate": {"$lte": p["date"]}}},
        *q1_group_and_sort(),
    ]


def q2(p):
    return "part", [
        {"$match": {"size": p["size"], "type": {"$regex": p["type"] + "$"}}},
        *join("partsupp", "_id", "partkey", "ps"),
        *join("supplier", "ps.suppkey", "_id", "s"),
        *join("nation", "s.nationkey", "_id", "n"),
        *join("region", "n.regionkey", "_id", "r"),
        {"$match": {"r.name": p["region"]}},
        # Subquery: minimum cost of each part in the region, then keep the
        # suppliers whose cost is that minimum.
        {"$group": {"_id": "$_id", "min_cost": {"$min": "$ps.supplycost"},
                    "rows": {"$push": "$$ROOT"}}},
        {"$unwind": "$rows"},
        {"$match": {"$expr": {"$eq": ["$rows.ps.supplycost", "$min_cost"]}}},
        {"$project": {"_id": 0, "s_acctbal": "$rows.s.acctbal",
                      "s_name": "$rows.s.name", "n_name": "$rows.n.name",
                      "p_partkey": "$rows._id", "p_mfgr": "$rows.mfgr",
                      "s_address": "$rows.s.address", "s_phone": "$rows.s.phone",
                      "s_comment": "$rows.s.comment"}},
        Q2_SORT,
    ]


def q3(p):
    return "customer", [
        {"$match": {"mktsegment": p["segment"]}},
        *join("orders", "_id", "custkey", "o",
              [{"$match": {"orderdate": {"$lt": p["date1"]}}}]),
        *join("lineitem", "o._id", "orderkey", "l",
              [{"$match": {"shipdate": {"$gt": p["date2"]}}}]),
        {"$group": {"_id": "$o._id",
                    "revenue": {"$sum": revenue("$l.extendedprice", "$l.discount")},
                    "o_orderdate": {"$first": "$o.orderdate"},
                    "o_shippriority": {"$first": "$o.shippriority"}}},
        {"$sort": {"revenue": -1, "o_orderdate": 1}},
        {"$project": {"_id": 0, "l_orderkey": "$_id", "revenue": 1,
                      "o_orderdate": 1, "o_shippriority": 1}},
    ]


def q4(p):
    return "region", [
        {"$match": {"name": p["region"]}},
        *join("nation", "_id", "regionkey", "n"),
        *join("customer", "n._id", "nationkey", "c"),
        *join("orders", "c._id", "custkey", "o",
              [{"$match": {"orderdate": {"$gte": p["date"], "$lt": p["date_end"]}}}]),
        *join("lineitem", "o._id", "orderkey", "l"),
        *join("supplier", "l.suppkey", "_id", "s"),
        # Customer and supplier in the same nation
        {"$match": {"$expr": {"$eq": ["$s.nationkey", "$c.nationkey"]}}},
        {"$group": {"_id": "$n.name",
                    "revenue": {"$sum": revenue("$l.extendedprice", "$l.discount")}}},
        {"$sort": {"revenue": -1}},
        {"$project": {"_id": 0, "n_name": "$_id", "revenue": 1}},
    ]
