"""
Check that the MongoDB queries are correct.

DuckDB, a relational database that runs inside Python (pip install duckdb),
reads the same .tbl files as tables and runs the original SQL of the
statement. Every MongoDB result must give the same rows.

    python verify_sql.py --data tpch-data --name sf02

It prints OK or DIFF for every query and model.
"""
import argparse
import os

import duckdb

from config import PARAMS, database_name
from helpers import connect, pipeline_of
from models import MODELS, QUERIES
from tpch_files import COLUMNS, DATES, DECIMALS, INTEGERS

# The SQL of Appendix B of the statement, with the same parameters.
SQL = {
    "q1": """select l_returnflag, l_linestatus, sum(l_quantity), sum(l_extendedprice),
                sum(l_extendedprice*(1-l_discount)),
                sum(l_extendedprice*(1-l_discount)*(1+l_tax)),
                avg(l_quantity), avg(l_extendedprice), avg(l_discount), count(*)
             from lineitem where l_shipdate <= date '{date}'
             group by l_returnflag, l_linestatus order by l_returnflag, l_linestatus""",
    "q2": """select s_acctbal, s_name, n_name, p_partkey, p_mfgr, s_address, s_phone, s_comment
             from part, supplier, partsupp, nation, region
             where p_partkey = ps_partkey and s_suppkey = ps_suppkey and p_size = {size}
               and p_type like '%{type}' and s_nationkey = n_nationkey
               and n_regionkey = r_regionkey and r_name = '{region}'
               and ps_supplycost = (select min(ps_supplycost)
                   from partsupp, supplier, nation, region
                   where p_partkey = ps_partkey and s_suppkey = ps_suppkey
                     and s_nationkey = n_nationkey and n_regionkey = r_regionkey
                     and r_name = '{region}')
             order by s_acctbal desc, n_name, s_name, p_partkey""",
    "q3": """select l_orderkey, sum(l_extendedprice*(1-l_discount)) as revenue,
                o_orderdate, o_shippriority
             from customer, orders, lineitem
             where c_mktsegment = '{segment}' and c_custkey = o_custkey
               and l_orderkey = o_orderkey and o_orderdate < date '{date1}'
               and l_shipdate > date '{date2}'
             group by l_orderkey, o_orderdate, o_shippriority
             order by revenue desc, o_orderdate""",
    "q4": """select n_name, sum(l_extendedprice*(1-l_discount)) as revenue
             from customer, orders, lineitem, supplier, nation, region
             where c_custkey = o_custkey and l_orderkey = o_orderkey
               and l_suppkey = s_suppkey and c_nationkey = s_nationkey
               and s_nationkey = n_nationkey and n_regionkey = r_regionkey
               and r_name = '{region}' and o_orderdate >= date '{date}'
               and o_orderdate < date '{date}' + interval 1 year
             group by n_name order by revenue desc""",
}

# Fields of the MongoDB results, in the same order as the SQL columns.
FIELDS = {
    "q1": ["_id.l_returnflag", "_id.l_linestatus", "sum_qty", "sum_base_price",
           "sum_disc_price", "sum_charge", "avg_qty", "avg_price", "avg_disc",
           "count_order"],
    "q2": ["s_acctbal", "s_name", "n_name", "p_partkey", "p_mfgr", "s_address",
           "s_phone", "s_comment"],
    "q3": ["l_orderkey", "revenue", "o_orderdate", "o_shippriority"],
    "q4": ["n_name", "revenue"],
}
PREFIX = {"region": "r_", "nation": "n_", "supplier": "s_", "customer": "c_",
          "part": "p_", "partsupp": "ps_", "orders": "o_", "lineitem": "l_"}


def load_tables(folder):
    """Create one DuckDB table per .tbl file, with the TPC-H column names."""
    con = duckdb.connect()
    for table, columns in COLUMNS.items():
        path = os.path.join(folder, table + ".tbl")
        path = path + ".gz" if os.path.exists(path + ".gz") else path
        types = {PREFIX[table] + c: ("BIGINT" if c in INTEGERS else "DOUBLE" if c in DECIMALS
                                     else "DATE" if c in DATES else "VARCHAR")
                 for c in columns}
        con.execute(f"create table {table} as select * from read_csv('{path}', "
                    f"delim='|', header=false, quote='', null_padding=true, "
                    f"columns={types})")
    return con


def value(document, field):
    for part in field.split("."):          # "_id.l_returnflag" -> nested field
        document = document[part]
    return document.date() if hasattr(document, "date") else document


def same_rows(mongo_rows, sql_rows):
    """Same number of rows and same values (decimals within 1 millionth)."""
    if len(mongo_rows) != len(sql_rows):
        return False
    key = lambda row: tuple(round(v, 2) if isinstance(v, float) else str(v) for v in row)
    for a, b in zip(sorted(mongo_rows, key=key), sorted(sql_rows, key=key)):
        for x, y in zip(a, b):
            if isinstance(x, float) or isinstance(y, float):
                if abs(x - y) > 1e-6 * max(1, abs(x), abs(y)):
                    return False
            elif x != y:
                return False
    return True


parser = argparse.ArgumentParser()
parser.add_argument("--data", required=True, help="folder with the .tbl files")
parser.add_argument("--name", required=True, help="dataset loaded in step 2")
args = parser.parse_args()

con = load_tables(args.data)
client = connect()
for query in QUERIES:
    params = {k: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else v
              for k, v in PARAMS[query].items()}
    sql_rows = con.execute(SQL[query].format(**params)).fetchall()
    for model_id, model in MODELS.items():
        collection, pipeline = pipeline_of(model, query)
        db = client[database_name(model_id, args.name)]
        documents = db[collection].aggregate(pipeline, allowDiskUse=True)
        mongo_rows = [tuple(value(d, f) for f in FIELDS[query]) for d in documents]
        status = "OK" if same_rows(mongo_rows, sql_rows) else "DIFF"
        print(f"{query} {model.NAME:16s} {len(mongo_rows):6d} rows (SQL {len(sql_rows):6d})  {status}")
