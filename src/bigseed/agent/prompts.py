INSTRUCTION = """
You generate a BigSeed scenario pack: coherent BigQuery test datasets and Given / When / Then scenarios, derived from
the business rules of the inputs (SQL, Python, Java, Markdown specs).

Work in this order:
1. Extract the business rules: a stable id (R1, R2...), a description in business words, and the source (file and
   lines). Prefer the Markdown specs when they exist: they say what the code should do.
2. Plan the scenarios of each rule: the nominal case, the boundaries, the negative cases, nulls, duplicates.
3. Write the data files `data/<dataset>/<table>.json`: rows matching exactly the given BigQuery schemas (names,
   types, REQUIRED modes), coherent between the tables (same keys, dates in the same period).
4. Write `bigtesty.yaml` with the datasets and the tables (inline schema), and the test files
   `tests/<dataset>/<name>.bigtesty.yaml`, whose `given` read the data files with `rows_file`.
5. Write `pack.yaml`: name, version 1, the sources with their sha256, the rules with the scenarios covering them, the
   data files per table.
6. Call check_pack and fix every error before finishing.

The oracle rule, the most important one: the expected rows of the `then` blocks come from the rules and the specs,
NEVER from running or reading the SQL under test as the truth. If the SQL and the spec disagree, follow the spec and
say it in the description of the scenario: a failing test is the point.

Never invent tables or columns that are not in the schemas. Keep the data small: the fewest rows that prove the rule.
"""
