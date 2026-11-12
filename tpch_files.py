"""
Reading the TPC-H data files.

The data comes as one text file per table (e.g. orders.tbl), with one row per
line and the columns separated by '|':

    1|7381|O|181585.13|1996-01-02|5-LOW|Clerk#000000951|0|nstructions sleep...|

The files can also be compressed (orders.tbl.gz), as in the optional dataset.
This module turns each line into a Python dictionary with the right types.
"""
import gzip
import os
from datetime import datetime

# Column names of every table, in the order they appear in the files.
COLUMNS = {
    "region":   ["regionkey", "name", "comment"],
    "nation":   ["nationkey", "name", "regionkey", "comment"],
    "supplier": ["suppkey", "name", "address", "nationkey", "phone", "acctbal",
                 "comment"],
    "customer": ["custkey", "name", "address", "nationkey", "phone", "acctbal",
                 "mktsegment", "comment"],
    "part":     ["partkey", "name", "mfgr", "brand", "type", "size", "container",
                 "retailprice", "comment"],
    "partsupp": ["partkey", "suppkey", "availqty", "supplycost", "comment"],
    "orders":   ["orderkey", "custkey", "orderstatus", "totalprice", "orderdate",
                 "orderpriority", "clerk", "shippriority", "comment"],
    "lineitem": ["orderkey", "partkey", "suppkey", "linenumber", "quantity",
                 "extendedprice", "discount", "tax", "returnflag", "linestatus",
                 "shipdate", "commitdate", "receiptdate", "shipinstruct",
                 "shipmode", "comment"],
}

# Columns that are not text.
INTEGERS = {"regionkey", "nationkey", "suppkey", "custkey", "partkey", "orderkey",
            "size", "availqty", "shippriority", "linenumber"}
DECIMALS = {"acctbal", "retailprice", "supplycost", "totalprice", "quantity",
            "extendedprice", "discount", "tax"}
DATES = {"orderdate", "shipdate", "commitdate", "receiptdate"}


def convert(column, text):
    if column in INTEGERS:
        return int(text)
    if column in DECIMALS:
        return float(text)
    if column in DATES:
        return datetime.fromisoformat(text)     # MongoDB stores it as a Date
    return text


def read_table(folder, table, keep):
    """Yield one dictionary per row, with only the columns listed in `keep`.

    Example: read_table("tpch-data", "region", ["regionkey", "name"])
             -> {"regionkey": 0, "name": "AFRICA"}, {"regionkey": 1, ...}, ...
    """
    path = os.path.join(folder, table + ".tbl")
    if os.path.exists(path + ".gz"):
        file = gzip.open(path + ".gz", "rt", encoding="utf-8")
    else:
        file = open(path, encoding="utf-8")
    positions = [COLUMNS[table].index(column) for column in keep]
    with file:
        for line in file:
            values = line.split("|")
            yield {column: convert(column, values[pos])
                   for column, pos in zip(keep, positions)}


class TPCH:
    """Access to one TPC-H dataset (one folder of .tbl files).

    The small tables are kept in memory as dictionaries indexed by their key,
    so that a document can copy, for instance, the name of a customer's
    nation:  tpch.nations[customer["nationkey"]]["name"].
    The two big tables (orders and lineitem) are read row by row.
    """

    def __init__(self, folder):
        self.folder = folder
        self.regions = {r["regionkey"]: r for r in read_table(
            folder, "region", ["regionkey", "name"])}
        self.nations = {n["nationkey"]: n for n in read_table(
            folder, "nation", ["nationkey", "name", "regionkey"])}
        self.suppliers = {s["suppkey"]: s for s in read_table(
            folder, "supplier", ["suppkey", "name", "address", "nationkey",
                                 "phone", "acctbal", "comment"])}
        self.customers = {c["custkey"]: c for c in read_table(
            folder, "customer", ["custkey", "nationkey", "mktsegment"])}

    def parts(self):
        return read_table(self.folder, "part", ["partkey", "mfgr", "type", "size"])

    def partsupps(self):
        return read_table(self.folder, "partsupp",
                          ["partkey", "suppkey", "supplycost"])

    def orders(self):
        return read_table(self.folder, "orders",
                          ["orderkey", "custkey", "orderdate", "shippriority"])

    def lineitems(self):
        return read_table(self.folder, "lineitem",
                          ["orderkey", "partkey", "suppkey", "linenumber",
                           "quantity", "extendedprice", "discount", "tax",
                           "returnflag", "linestatus", "shipdate"])

    def suppliers_by_part(self):
        """{partkey: [its partsupp rows]}  (4 per part)."""
        result = {}
        for ps in self.partsupps():
            result.setdefault(ps["partkey"], []).append(ps)
        return result

    def orders_with_lines(self):
        """Yield (order, [its line items]) for every order.

        lineitem.tbl is sorted by order key, so the lines of an order are
        consecutive: we collect them until the order key changes.
        """
        orders = {o["orderkey"]: o for o in self.orders()}
        current_key, lines = None, []
        for line in self.lineitems():
            if line["orderkey"] != current_key and lines:
                yield orders[current_key], lines
                lines = []
            current_key = line["orderkey"]
            lines.append(line)
        if lines:
            yield orders[current_key], lines
