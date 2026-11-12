"""
M1 - Order-rooted.

    orders : one document per order, with its 1-7 line items embedded in the
             array "lines", and the customer attributes copied.
    parts  : one document per part, with its 4 suppliers embedded.

Example documents: examples/m1.json

    orders { _id, orderdate, shippriority, mktsegment, cust_nation, ...,
             lines: [ { shipdate, quantity, extendedprice, ... }, ... ] }
    parts  { _id, mfgr, type, size,
             suppliers: [ { supplycost, name, nation, region, ... }, ... ] }
"""
from models.common import (Q2_SORT, customer_copy, part_with_suppliers,
                           q1_group_and_sort, revenue)

NAME = "M1 order-rooted"


# ---------------------------------------------------------------- documents --
def order_document(order, lines, tpch):
    return {
        "_id": order["orderkey"],
        "orderdate": order["orderdate"],
        "shippriority": order["shippriority"],
        **customer_copy(order, tpch),
        "lines": [{
            "linenumber": l["linenumber"],
            "returnflag": l["returnflag"],
            "linestatus": l["linestatus"],
            "quantity": l["quantity"],
            "extendedprice": l["extendedprice"],
            "discount": l["discount"],
            "tax": l["tax"],
            "shipdate": l["shipdate"],
            "supp_nationkey": tpch.suppliers[l["suppkey"]]["nationkey"],
        } for l in lines],
    }


def documents(tpch):
    """Yield (collection, document) for every document of the model."""
    by_part = tpch.suppliers_by_part()
    for part in tpch.parts():
        yield "parts", part_with_suppliers(part, by_part[part["partkey"]], tpch)
    for order, lines in tpch.orders_with_lines():
        yield "orders", order_document(order, lines, tpch)


# ------------------------------------------------------------------ indexes --
# Equality fields first, range field last. "lines.shipdate" is a field inside
# the array, so the index is multikey: one entry per line.
INDEXES = {
    "orders": [[("mktsegment", 1), ("orderdate", 1), ("lines.shipdate", 1)],
               [("cust_region", 1), ("orderdate", 1)]],
    "parts": [[("size", 1), ("type", 1)]],
}


# ------------------------------------------------------------------ queries --
def q1(p):
    return "orders", [
        # The first $match discards whole orders, the second one single lines.
        {"$match": {"lines.shipdate": {"$lte": p["date"]}}},
        {"$project": {"_id": 0, "lines": 1}},     # keep only what Q1 needs
        {"$unwind": "$lines"},
        {"$match": {"lines.shipdate": {"$lte": p["date"]}}},
        *q1_group_and_sort("$lines."),
    ]


def q2(p):
    """Everything is inside the part: no join and no $group needed."""
    in_region = {"$filter": {"input": "$suppliers", "as": "s",
                             "cond": {"$eq": ["$$s.region", p["region"]]}}}
    return "parts", [
        {"$match": {"size": p["size"], "type": {"$regex": p["type"] + "$"},
                    "suppliers.region": p["region"]}},
        {"$set": {"candidates": in_region}},
        {"$set": {"min_cost": {"$min": "$candidates.supplycost"}}},
        {"$unwind": "$candidates"},
        {"$match": {"$expr": {"$eq": ["$candidates.supplycost", "$min_cost"]}}},
        {"$project": {"_id": 0, "s_acctbal": "$candidates.acctbal",
                      "s_name": "$candidates.name", "n_name": "$candidates.nation",
                      "p_partkey": "$_id", "p_mfgr": "$mfgr",
                      "s_address": "$candidates.address",
                      "s_phone": "$candidates.phone",
                      "s_comment": "$candidates.comment"}},
        Q2_SORT,
    ]


def sum_revenue(lines):
    """Revenue of an array of lines: sum of extendedprice * (1 - discount)."""
    return {"$sum": {"$map": {"input": lines, "as": "l",
                              "in": revenue("$$l.extendedprice", "$$l.discount")}}}


def q3(p):
    """The order is the group: GROUP BY orderkey is not needed."""
    shipped_later = {"$filter": {"input": "$lines", "as": "l",
                                 "cond": {"$gt": ["$$l.shipdate", p["date2"]]}}}
    return "orders", [
        {"$match": {"mktsegment": p["segment"], "orderdate": {"$lt": p["date1"]},
                    "lines.shipdate": {"$gt": p["date2"]}}},
        {"$project": {"_id": 0, "l_orderkey": "$_id",
                      "revenue": sum_revenue(shipped_later),
                      "o_orderdate": "$orderdate", "o_shippriority": "$shippriority"}},
        {"$sort": {"revenue": -1, "o_orderdate": 1}},
    ]


def q4(p):
    same_nation_lines = {"$filter": {"input": "$lines", "as": "l", "cond": {
        "$eq": ["$$l.supp_nationkey", "$cust_nationkey"]}}}
    return "orders", [
        {"$match": {"cust_region": p["region"],
                    "orderdate": {"$gte": p["date"], "$lt": p["date_end"]}}},
        {"$project": {"cust_nation": 1, "local": same_nation_lines}},
        {"$match": {"local.0": {"$exists": True}}},   # at least one local line
        {"$group": {"_id": "$cust_nation", "revenue": {"$sum": sum_revenue("$local")}}},
        {"$sort": {"revenue": -1}},
        {"$project": {"_id": 0, "n_name": "$_id", "revenue": 1}},
    ]
