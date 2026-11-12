# Lab 1 – Document-based data modelling (TPC-H on MongoDB)

## How the code is organised

```
config.py               MongoDB address and the parameters of the queries
tpch_files.py           reads the TPC-H .tbl files into Python dictionaries
models/                 ONE FILE PER MODEL: documents, indexes and the 4 queries
   common.py            pieces shared by several models
   m0_normalised.py     M0: one collection per table, joins with $lookup
   m1_order_rooted.py   M1: lines embedded in the order, suppliers in the part
   m2_line_rooted.py    M2: flat line items and part-supplier pairs
   p_proposed.py        P:  lineitem of M2 + same_nation, parts of M1
examples/               one real document per collection, one JSON file per model
sample_data/            a tiny hand-made TPC-H dataset (a few rows per table)
helpers.py              insert in batches, create/drop indexes, run, explain()
step1_sample_inserts.py ... step5_extra_experiments.py   the steps, in order
verify_sql.py           checks every MongoDB result against the original SQL
DISCUSSION.md           why the proposal performs as it does
results/                results saved by steps 4 and 5
```

Every file in `models/` has the same four parts:

* `documents(tpch)` builds every document of the model, returning `(collection, document)`.
* `INDEXES` lists the indexes of each collection.
* `q1(p)` … `q4(p)` return `(collection, pipeline)` with the Aggregation Framework.

To understand a model, read its file from top to bottom; to compare models, open two of them side by side.

## Where each item of the statement is

| Statement | File |
|---|---|
| Data model and sample dataset | `models/`, `sample_data/`, `step2_load_dataset.py` |
| Optional dataset (bonus) and larger dataset | `step2_load_dataset.py` with `--data tpch-data` or an SF 1 folder |
| Inserts of sample documents | `step1_sample_inserts.py` with `examples/*.json` |
| The 4 queries with the Aggregation Framework | `q1` … `q4` in each file of `models/` |
| Discussion with `explain()` | `step3_run_queries.py`, `step4_benchmark.py`, `DISCUSSION.md` |

## Running it

You need MongoDB 7 or 8 running on `localhost:27017` (or set `MONGO_URI`) and Python 3.10+.

```bash
pip install -r requirements.txt

# 1. Insert the example documents of each model and print them
python step1_sample_inserts.py

# 2. Load a dataset into the four models (databases m0_<name>, m1_<name>, m2_<name>, p_<name>)
python step2_load_dataset.py --data sample_data --name sample      # tiny, instant
git clone https://github.com/aleaugustoplus/tpch-data
python step2_load_dataset.py --data tpch-data --name sf02          # about 1 minute

# Check that every query gives the same rows as the original SQL (all must say OK)
python verify_sql.py --data tpch-data --name sf02

# 3. Run the queries: time, documents read (explain) and first rows
python step3_run_queries.py --name sf02
python step3_run_queries.py --name sf02 --model m1 --query q3      # just one

# 4. Benchmark: phase 2 without indexes, phase 3 with indexes (about 10 minutes)
python step4_benchmark.py --name sf02

# 5. Extra experiments: index for Q1, M1 Q3 index, storage, write costs
python step5_extra_experiments.py --name sf02
```

In phase 2, M0 reaches the 3-minute limit (`config.py`) in Q3 and Q4: without an index, every `$lookup` reads the whole joined collection once per document. That is part of the result, not an error.

### Larger dataset (SF 1, 6 million line items)

```bash
pip install tpchgen-cli
tpchgen-cli -s 1 --output-dir=sf1
python step2_load_dataset.py --data sf1 --name sf1                 # about 3 minutes
python step4_benchmark.py --name sf1 --repetitions 3               # about 40 minutes
```

Loading SF 1 needs around 2 GB of free memory.
# MongoDB_lab1
# MongoDB_lab1
