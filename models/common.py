"""
Pieces shared by several models.

Building blocks of the documents (which fields are copied from other tables)
and pieces of the queries that are the same in every model.
"""


# ---------------------------------------------------------------- documents --
def line_id(orderkey, linenumber):
    """_id of a line item: order 1000, line 3 -> 10003 (lines go from 1 to 7)."""
    return orderkey * 10 + linenumber


def customer_copy(order, tpch):
    """Customer attributes copied into an order or a line (M1, M2 and P).

    Only the stable attributes that the queries need are copied: the segment
    (Q3) and the nation and region (Q4).
    """
    customer = tpch.customers[order["custkey"]]
    nation = tpch.nations[customer["nationkey"]]
    return {
        "custkey": order["custkey"],
        "mktsegment": customer["mktsegment"],
        "cust_nationkey": customer["nationkey"],
        "cust_nation": nation["name"],
        "cust_region": tpch.regions[nation["regionkey"]]["name"],
    }


def flat_line(order, line, tpch):
    """One line item with its order and customer data at root level (M2 and P)."""
    return {
        "_id": line_id(order["orderkey"], line["linenumber"]),
        "orderkey": order["orderkey"],
        "linenumber": line["linenumber"],
        "orderdate": order["orderdate"],
        "shippriority": order["shippriority"],
        **customer_copy(order, tpch),
        "returnflag": line["returnflag"],
        "linestatus": line["linestatus"],
        "quantity": line["quantity"],
        "extendedprice": line["extendedprice"],
        "discount": line["discount"],
        "tax": line["tax"],
        "shipdate": line["shipdate"],
        "supp_nationkey": tpch.suppliers[line["suppkey"]]["nationkey"],
    }


def part_with_suppliers(part, partsupps, tpch):
    """One part with its 4 suppliers embedded (M1 and P)."""
    suppliers = []
    for ps in partsupps:
        supplier = tpch.suppliers[ps["suppkey"]]
        nation = tpch.nations[supplier["nationkey"]]
        suppliers.append({
            "suppkey": ps["suppkey"],
            "supplycost": ps["supplycost"],
            "name": supplier["name"],
            "address": supplier["address"],
            "phone": supplier["phone"],
            "acctbal": supplier["acctbal"],
            "comment": supplier["comment"],
            "nation": nation["name"],
            "region": tpch.regions[nation["regionkey"]]["name"],
        })
    return {"_id": part["partkey"], "mfgr": part["mfgr"], "type": part["type"],
            "size": part["size"], "suppliers": suppliers}


# ------------------------------------------------------------------ queries --
def revenue(price="$extendedprice", discount="$discount"):
    """extendedprice * (1 - discount), as an aggregation expression."""
    return {"$multiply": [price, {"$subtract": [1, discount]}]}


def q1_group_and_sort(prefix="$"):
    """The $group and $sort stages of Q1.

    `prefix` is where the line fields are: "$" if they are at root level,
    "$lines." if they come from the embedded array of M1.
    """
    price, discount = prefix + "extendedprice", prefix + "discount"
    return [
        {"$group": {
            "_id": {"l_returnflag": prefix + "returnflag",
                    "l_linestatus": prefix + "linestatus"},
            "sum_qty": {"$sum": prefix + "quantity"},
            "sum_base_price": {"$sum": price},
            "sum_disc_price": {"$sum": revenue(price, discount)},
            "sum_charge": {"$sum": {"$multiply": [revenue(price, discount),
                                                  {"$add": [1, prefix + "tax"]}]}},
            "avg_qty": {"$avg": prefix + "quantity"},
            "avg_price": {"$avg": price},
            "avg_disc": {"$avg": discount},
            "count_order": {"$sum": 1},
        }},
        {"$sort": {"_id.l_returnflag": 1, "_id.l_linestatus": 1}},
    ]


# ORDER BY of Q2: s_acctbal desc, n_name, s_name, p_partkey
Q2_SORT = {"$sort": {"s_acctbal": -1, "n_name": 1, "s_name": 1, "p_partkey": 1}}
