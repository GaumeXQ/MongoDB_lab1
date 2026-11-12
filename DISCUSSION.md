# Why the proposal performs as expected (or not)

Times measured at SF 1 (6 million line items) on 2 vCPU, median, in ms.
Your machine will give other absolute times; the ranking should be the same.
The full reasoning is in the report.

## Phase 1: design from the queries (nothing measured)

* Q1, Q3 and Q4 aggregate line items; Q2 needs a part with its suppliers.
* Part–supplier is one-to-few (4 per part): embed. Order–line is one-to-few
  (1–7 per order): embed (M1) or flatten (M2), both legitimate.
  Customer–order is unbounded: never embed, copy only segment, nation, region.
* Candidates: M0 normalised (baseline), M1 order-rooted, M2 line-rooted.

## Phase 2: without indexes (only `_id`)

|    | M0 | M1 | M2 |
|----|---:|---:|---:|
| Q1 | 9,817 | 18,296 | 11,076 |
| Q2 | > 180 s | **100** | 476 |
| Q3 | > 180 s | **936** | 2,865 |
| Q4 | > 180 s | **938** | 2,634 |

* M0 never finishes Q2–Q4: a `$lookup` without index reads the whole joined
  collection once per document.
* M1 wins Q2–Q4: every model reads its whole collection, and M1 has 1.5 M
  orders where M2 has 6 M lines.
* M1 loses Q1: `$unwind` of every order (and explain shows the classic engine).
* **Choice after phase 2: M1.**

## Phase 3: with indexes, and changes suggested by `explain()`

|    | M0 | M1 | M2 | P (new) |
|----|---:|---:|---:|---:|
| Q1 | 10,155 | 19,556 | 10,101 | **9,822** |
| Q2 | 288 | 14.8 | **13.6** | 14.0 |
| Q3 | 7,733 | **176** | 207 | 218 |
| Q4 | 8,331 | 360 | 398 | **41** |

* Q4 read 46 k (M1) and 368 k (M2) documents only to compare two fields,
  which an index cannot do. Precomputing `same_nation` and indexing it gave
  the new model **P**: 41 ms. Without an index the field is useless, which
  is why P could only appear in this phase.
* M1 Q3: adding `lines.shipdate` (multikey) to the index cut the orders read
  from 147,126 to 11,620.
* An index on `shipdate` for Q1 was rejected: Q1 selects 98.6 % of the lines
  and the index made it 2.7 times slower than a full scan.

**Final proposal: P with indexes; M1 if indexes are not allowed.**
Costs of P: 1.5 times the data of M1, a supplier change rewrites 80
documents, and an order is 4 documents (no longer atomic without a
transaction). Acceptable because the workload only reads (OLAP).

## Learning outcomes (in our own words)

TO COMPLETE by the students.
