"""
P - Proposed model (designed in phase 3, after comparing with indexes).

    lineitem : the flat lineitem of M2, plus the field same_nation, computed
               when the document is created: customer nation == supplier nation.
    parts    : the parts collection of M1 (suppliers embedded).

Why: with indexes, Q4 still read many documents only to compare two fields,
which an index cannot do. A precomputed boolean can be indexed. Without an
index the field is useless, so this model only makes sense with indexes.

Example documents: examples/p.json
"""
from models import m1_order_rooted, m2_line_rooted
from models.common import flat_line, part_with_suppliers, revenue

NAME = "P proposed"


# ---------------------------------------------------------------- documents --
def line_document(order, line, tpch):
    document = flat_line(order, line, tpch)
    document["same_nation"] = document["cust_nationkey"] == document["supp_nationkey"]
    return document


def documents(tpch):
    """Yield (collection, document) for every document of the model."""
    by_part = tpch.suppliers_by_part()
    for part in tpch.parts():
        yield "parts", part_with_suppliers(part, by_part[part["partkey"]], tpch)
    for order, lines in tpch.orders_with_lines():
        for line in lines:
            yield "lineitem", line_document(order, line, tpch)


# ------------------------------------------------------------------ indexes --
INDEXES = {
    "lineitem": [[("mktsegment", 1), ("orderdate", 1), ("shipdate", 1)],
                 [("cust_region", 1), ("same_nation", 1), ("orderdate", 1)]],
    "parts": [[("size", 1), ("type", 1)]],
}


# ------------------------------------------------------------------ queries --
q1 = m2_line_rooted.q1          # same lineitem as M2
q2 = m1_order_rooted.q2         # same parts as M1
q3 = m2_line_rooted.q3


def q4(p):
    """Like M2, but the two-field comparison is now an indexed equality."""
    return "lineitem", [
        {"$match": {"cust_region": p["region"], "same_nation": True,
                    "orderdate": {"$gte": p["date"], "$lt": p["date_end"]}}},
        {"$group": {"_id": "$cust_nation", "revenue": {"$sum": revenue()}}},
        {"$sort": {"revenue": -1}},
        {"$project": {"_id": 0, "n_name": "$_id", "revenue": 1}},
    ]
