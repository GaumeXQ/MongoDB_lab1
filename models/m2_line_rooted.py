"""
M2 - Line-rooted.

    lineitem : one flat document per line item, with the order and customer
               attributes copied at root level.
    partsupp : one flat document per part-supplier pair, with the part and
               supplier attributes copied.

Example documents: examples/m2.json

    lineitem { _id, orderkey, orderdate, mktsegment, cust_region, shipdate,
               quantity, extendedprice, discount, ..., supp_nationkey }
    partsupp { _id, partkey, mfgr, type, size, supplycost, s_name, nation, region, ... }
"""
from models.common import Q2_SORT, flat_line, q1_group_and_sort, revenue

NAME = "M2 line-rooted"


# ---------------------------------------------------------------- documents --
def partsupp_document(part, ps, tpch):
    supplier = tpch.suppliers[ps["suppkey"]]
    nation = tpch.nations[supplier["nationkey"]]
    return {
        "_id": part["partkey"] * 10_000_000 + ps["suppkey"],
        "partkey": part["partkey"],
        "mfgr": part["mfgr"], "type": part["type"], "size": part["size"],
        "suppkey": ps["suppkey"],
        "supplycost": ps["supplycost"],
        "s_name": supplier["name"],
        "s_address": supplier["address"],
        "s_phone": supplier["phone"],
        "s_acctbal": supplier["acctbal"],
        "s_comment": supplier["comment"],
        "nation": nation["name"],
        "region": tpch.regions[nation["regionkey"]]["name"],
    }


def documents(tpch):
    """Yield (collection, document) for every document of the model."""
    by_part = tpch.suppliers_by_part()
    for part in tpch.parts():
        for ps in by_part[part["partkey"]]:
            yield "partsupp", partsupp_document(part, ps, tpch)
    for order, lines in tpch.orders_with_lines():
        for line in lines:
            yield "lineitem", flat_line(order, line, tpch)


# ------------------------------------------------------------------ indexes --
INDEXES = {
    "lineitem": [[("mktsegment", 1), ("orderdate", 1), ("shipdate", 1)],
                 [("cust_region", 1), ("orderdate", 1)]],
    "partsupp": [[("size", 1), ("type", 1), ("region", 1)]],
}


# ------------------------------------------------------------------ queries --
def q1(p):
    return "lineitem", [
        {"$match": {"shipdate": {"$lte": p["date"]}}},
        *q1_group_and_sort(),
    ]


def q2(p):
    """The 4 suppliers of a part are 4 documents: $group puts them together."""
    return "partsupp", [
        {"$match": {"size": p["size"], "type": {"$regex": p["type"] + "$"},
                    "region": p["region"]}},
        {"$group": {"_id": "$partkey", "min_cost": {"$min": "$supplycost"},
                    "rows": {"$push": "$$ROOT"}}},
        {"$unwind": "$rows"},
        {"$match": {"$expr": {"$eq": ["$rows.supplycost", "$min_cost"]}}},
        {"$project": {"_id": 0, "s_acctbal": "$rows.s_acctbal",
                      "s_name": "$rows.s_name", "n_name": "$rows.nation",
                      "p_partkey": "$rows.partkey", "p_mfgr": "$rows.mfgr",
                      "s_address": "$rows.s_address", "s_phone": "$rows.s_phone",
                      "s_comment": "$rows.s_comment"}},
        Q2_SORT,
    ]


def q3(p):
    return "lineitem", [
        {"$match": {"mktsegment": p["segment"], "orderdate": {"$lt": p["date1"]},
                    "shipdate": {"$gt": p["date2"]}}},
        {"$group": {"_id": "$orderkey", "revenue": {"$sum": revenue()},
                    "o_orderdate": {"$first": "$orderdate"},
                    "o_shippriority": {"$first": "$shippriority"}}},
        {"$sort": {"revenue": -1, "o_orderdate": 1}},
        {"$project": {"_id": 0, "l_orderkey": "$_id", "revenue": 1,
                      "o_orderdate": 1, "o_shippriority": 1}},
    ]


def q4(p):
    return "lineitem", [
        {"$match": {"cust_region": p["region"],
                    "orderdate": {"$gte": p["date"], "$lt": p["date_end"]},
                    # compares two fields of the same document
                    "$expr": {"$eq": ["$supp_nationkey", "$cust_nationkey"]}}},
        {"$group": {"_id": "$cust_nation", "revenue": {"$sum": revenue()}}},
        {"$sort": {"revenue": -1}},
        {"$project": {"_id": 0, "n_name": "$_id", "revenue": 1}},
    ]
