"""
Step 2 - Load a TPC-H dataset into the four models.

    python step2_load_dataset.py --data sample_data --name sample
    python step2_load_dataset.py --data tpch-data   --name sf02
    python step2_load_dataset.py --data sf1         --name sf1

--data is the folder with the .tbl (or .tbl.gz) files and --name is used in
the database names: m0_sf02, m1_sf02, m2_sf02 and p_sf02.
The same files give four different databases: what changes is how each model
groups and copies the rows into documents (see models/).
"""
import argparse
import time

from config import database_name
from helpers import connect, create_indexes, insert_in_batches
from models import MODELS
from tpch_files import TPCH

parser = argparse.ArgumentParser()
parser.add_argument("--data", required=True, help="folder with the .tbl files")
parser.add_argument("--name", required=True, help="name of the dataset, e.g. sf02")
parser.add_argument("--models", nargs="+", default=list(MODELS),
                    help="load only some models, e.g. --models m1 p")
args = parser.parse_args()

client = connect()
tpch = TPCH(args.data)      # reads the small tables (nation, customer, ...)

for model_id in args.models:
    model = MODELS[model_id]
    db = client[database_name(model_id, args.name)]
    client.drop_database(db.name)

    start = time.perf_counter()
    insert_in_batches(db, model.documents(tpch))
    create_indexes(db, model)
    seconds = time.perf_counter() - start

    counts = {c: db[c].estimated_document_count() for c in db.list_collection_names()}
    print(f"{model.NAME:16s} -> {db.name}: {counts}  ({seconds:.0f} s)")
