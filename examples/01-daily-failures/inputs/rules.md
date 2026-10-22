# Daily failures

The daily failures table gives, per day and per feature, the number of failed jobs, for the monitoring dashboard.

- A feature with at least 2 failed jobs on a day has one row for that day, with its number of failures.
- A feature with fewer than 2 failed jobs on a day is not reported for that day: one failure is noise.
- A failed job without feature name is ignored.
