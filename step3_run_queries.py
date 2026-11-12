"""
Step 3 - Run the four queries in every model and look at the results.

    python step3_run_queries.py --name sf02
    python step3_run_queries.py --name sf02 --model m1 --query q3

For each query it prints the time, how many documents MongoDB read (from
explain()), whether it used an index, and the first rows of the result.
"""
import argparse

from bson import json_util

from config import database_name
from helpers import connect, explain, pipeline_of, run
from models import MODELS, QUERIES

parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True, help="dataset loaded in step 2")
parser.add_argument("--model", choices=list(MODELS), help="only this model")
parser.add_argument("--query", choices=QUERIES, help="only this query")
args = parser.parse_args()

client = connect()
for model_id, model in MODELS.items():
    if args.model and model_id != args.model:
        continue
    db = client[database_name(model_id, args.name)]
    print(f"\n========== {model.NAME}")
    for query in QUERIES:
        if args.query and query != args.query:
            continue
        collection, pipeline = pipeline_of(model, query)
        rows, ms = run(db, collection, pipeline)
        stats = explain(db, collection, pipeline)
        print(f"\n{query.upper()} on db.{collection}: {len(rows)} rows in {ms:,.0f} ms, "
              f"{stats['docs_examined']:,} documents read, "
              f"{'with' if stats['uses_index'] else 'without'} index")
        for row in rows[:2]:
            print("   ", json_util.dumps(row))
