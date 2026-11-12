"""
Settings shared by all the scripts: where MongoDB is and the query parameters.
"""
import os
from datetime import datetime

# Address of the MongoDB server. Change it here or set the MONGO_URI variable.
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")

# Parameters of the four queries (the TPC-H validation values).
PARAMS = {
    "q1": {"date": datetime(1998, 9, 2)},
    "q2": {"size": 15, "type": "BRASS", "region": "EUROPE"},
    "q3": {"segment": "BUILDING", "date1": datetime(1995, 3, 15),
           "date2": datetime(1995, 3, 15)},
    "q4": {"region": "ASIA", "date": datetime(1994, 1, 1),
           "date_end": datetime(1995, 1, 1)},     # [DATE] + 1 year
}

# A query that takes longer than this is stopped (milliseconds).
TIME_LIMIT_MS = 180_000


def database_name(model, dataset):
    """Each model and dataset gets its own database, e.g. 'm1_sf02'."""
    return f"{model}_{dataset}"
