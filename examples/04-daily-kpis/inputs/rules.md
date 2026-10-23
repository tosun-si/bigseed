# Daily KPIs per store

`retail.daily_store_kpis` is reloaded each day by `load_daily_store_kpis.sql`, for the day of the parameter `run_date`.

- R1: the run replaces the rows of `run_date` only: the rows of the other days stay unchanged, and running it twice
  gives the same rows.
- R2: `revenue` is the sum of the amounts of the sales of the store on `run_date`, minus the amounts of its returns
  on `run_date`.
- R3: `visits` is the number of distinct visitors of the store on `run_date`; `conversionRate` is the number of sales
  divided by `visits`, rounded to 4 decimals, and 0 when there is no visit.
- R4: a store open (active) without any sale, return or visit on `run_date` has a row with 0 everywhere.
- R5: a closed store (not active) has no row.
