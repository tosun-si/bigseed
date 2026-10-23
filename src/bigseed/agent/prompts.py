INSTRUCTION = """
You generate a BigSeed scenario pack: coherent BigQuery test datasets and Given / When / Then scenarios, derived from
the business rules of the inputs (SQL, Python, Java, Markdown specs).

Work in this order:
1. Extract the business rules: a stable id (R1, R2...), a description in business words, and the source (file and
   lines). Prefer the Markdown specs when they exist: they say what the code should do.
2. Plan the scenarios: at least one per rule, and each scenario proves exactly ONE rule (nominal case, boundaries,
   negative cases, nulls, duplicates). Start its description with the rule id, e.g. "R2: ...".
3. Design ONE coherent dataset per input table, shared by all the scenarios: the rows of every scenario live together
   (distinct keys, features, days...) and each scenario checks its part of the output, with a WHERE in a `query` or
   `key_columns`. The same rows seed the environments: they must look like one realistic day of the system.
4. Write the files in ONE call to write_files:
   - `data/<dataset>/<table>.json`: the input tables only (the tables the code reads), one file per table, rows
     matching exactly the given BigQuery schemas (names, types, REQUIRED modes). Never a file for an output table,
     never a file per scenario, never expected rows in data/.
   - `bigtesty.yaml`: the datasets and the tables, with their inline schema.
   - `tests/<dataset>/<name>.bigtesty.yaml`: the scenarios, each with a snake_case `name`, a `description`, a
     `given` reading the data file of its table with `rows_file` (path relative to the test file), a `when` running
     the code under test (`sql_file: ../../inputs/<file>.sql`), and a `then` writing its expected rows inline
     (`expected`, with `key_columns` when the output has a key) or a `row_count`, never an `expected_file`. Without
     a `when`, the code never runs and a `row_count: 0` passes for nothing.
   - `pack.yaml`: `name` exactly the pack name given below, `version: 1`, a `description`, the `sources` with their
     sha256, the `rules` with the scenarios covering them (`<test file relative to tests/>::<scenario name>`), the
     `data` files per input table, and the `environments` given below (`environments: {}` when none is given).
5. Call check once. Fix every problem, uncovered rule and warning with write_files, then check again. Stop when check
   returns ok.

The oracle rule, the most important one: the expected rows of the `then` blocks come from the rules and the specs,
NEVER from running or reading the SQL under test as the truth. If the SQL and the spec disagree, follow the spec and
say it in the description of the scenario: a failing test is the point.

Never invent tables or columns that are not in the schemas. Keep the data small: the fewest rows that prove the rules.

The formats of the files, follow them exactly (lists stay lists, the keys are these ones), shown on another domain:

`pack.yaml`:
```yaml
name: <the pack name>
version: 1
description: <one sentence>
sources:
  - { path: inputs/rules.md, sha256: <sha256 given with the input> }
rules:
  - id: R1
    description: <the rule in business words>
    source: inputs/rules.md#L4
    scenarios: [sales/daily_revenue.bigtesty.yaml::r1_refunded_orders_are_excluded]
data:
  sales.orders: data/sales/orders.json
environments:
  uat:
    project: my-uat-project
    datasets: { sales: sales_uat }
```

`bigtesty.yaml`:
```yaml
location: <the BigQuery location given below>
datasets:
  - id: sales
    tables:
      - id: orders
        schema:
          - { name: orderId, type: STRING, mode: REQUIRED }
          - { name: amount, type: NUMERIC }
      - id: daily_revenue
        schema:
          - { name: day, type: DATE, mode: REQUIRED }
          - { name: revenue, type: NUMERIC, mode: REQUIRED }
```

`tests/sales/daily_revenue.bigtesty.yaml`:
```yaml
scenarios:
  - name: r1_refunded_orders_are_excluded
    description: "R1: the refunded order o3 of 2026-01-10 is not in the revenue of the day"
    given:
      - table: sales.orders
        rows_file: ../../data/sales/orders.json
    when:
      sql_file: ../../inputs/build_daily_revenue.sql
    then:
      - table: sales.daily_revenue
        key_columns: [day]
        expected:
          - { day: "2026-01-10", revenue: 30 }
      - query: SELECT * FROM sales.daily_revenue WHERE day = '2026-01-11'
        row_count: 0
```

`data/sales/orders.json`: a JSON list of rows, `[{"orderId": "o1", "amount": 10}, ...]`.
"""
