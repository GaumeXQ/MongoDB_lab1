"""
Step 4 - Benchmark: execution time of every query in every model.

    python step4_benchmark.py --name sf02
    python step4_benchmark.py --name sf1 --repetitions 3

Phase 2: only the _id index exists, so the times depend on the document
         structure alone (this is the objective of the lab).
Phase 3: the indexes of each model (models/*.py, INDEXES) are created and the
         same queries are run again.

Each time is the median of several runs, after one warm-up run. A query that
exceeds the time limit (config.py) is recorded as a timeout.
The results are saved in results/benchmark_<name>.json.
"""
import argparse
import json
import statistics

from pymongo.errors import ExecutionTimeout

from config import database_name
from helpers import connect, create_indexes, drop_indexes, explain, pipeline_of, run
from models import MODELS, QUERIES

parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True, help="dataset loaded in step 2")
parser.add_argument("--repetitions", type=int, default=5)
args = parser.parse_args()
client = connect()


def median_time(db, collection, pipeline):
    """Median time in ms, or None if the query hits the time limit."""
    times = []
    try:
        run(db, collection, pipeline)                  # warm-up, not counted
        for _ in range(args.repetitions):
            times.append(run(db, collection, pipeline)[1])
            if times[-1] > 20_000:                     # slow: one run is enough
                break
    except ExecutionTimeout:
        return None
    return statistics.median(times)


def measure_all():
    results = {}
    for model_id, model in MODELS.items():
        db = client[database_name(model_id, args.name)]
        for query in QUERIES:
            collection, pipeline = pipeline_of(model, query)
            ms = median_time(db, collection, pipeline)
            stats = explain(db, collection, pipeline) if ms is not None else {}
            results[f"{model_id}/{query}"] = {"ms": ms, **stats}
            shown = "timeout" if ms is None else f"{ms:,.1f} ms"
            print(f"  {model.NAME:16s} {query}: {shown}", flush=True)
    return results


print("Phase 2: without indexes")
for model_id in MODELS:
    drop_indexes(client[database_name(model_id, args.name)])
without_indexes = measure_all()

print("Phase 3: with indexes")
for model_id, model in MODELS.items():
    create_indexes(client[database_name(model_id, args.name)], model)
with_indexes = measure_all()

with open(f"results/benchmark_{args.name}.json", "w") as file:
    json.dump({"without_indexes": without_indexes, "with_indexes": with_indexes},
              file, indent=1)

# Summary table
print(f"\n{'':6s}" + "".join(f"{m:>12s}" for m in MODELS) + "   (ms)")
for title, results in (("Phase 2", without_indexes), ("Phase 3", with_indexes)):
    print(title)
    for query in QUERIES:
        cells = []
        for model_id in MODELS:
            ms = results[f"{model_id}/{query}"]["ms"]
            cells.append(f"{'timeout' if ms is None else f'{ms:,.1f}':>12s}")
        print(f"  {query.upper():4s}" + "".join(cells))
