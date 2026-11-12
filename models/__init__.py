"""The four data models. Each one is a module with the same parts:

    NAME         readable name
    documents()  builds every document: yields (collection, document)
    INDEXES      {collection: [index, ...]}
    q1() .. q4() the four queries: return (collection, pipeline)
"""
from models import m0_normalised, m1_order_rooted, m2_line_rooted, p_proposed

MODELS = {
    "m0": m0_normalised,
    "m1": m1_order_rooted,
    "m2": m2_line_rooted,
    "p": p_proposed,
}
QUERIES = ["q1", "q2", "q3", "q4"]
