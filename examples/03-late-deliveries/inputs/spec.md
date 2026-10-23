# Late deliveries

`logistics.late_deliveries` lists the late orders as of a date, the parameter `as_of_date`, for the delivery team.

- R1: a delivered order is late when it was delivered MORE than 2 days after its promised date. Delivered exactly 2
  days after the promised date is on time.
- R2: an order not delivered yet is late when `as_of_date` is more than 2 days after its promised date.
- R3: a cancelled order is never late.
- R4: each late order has the number of days of delay: delivery date (or `as_of_date` when not delivered) minus the
  promised date.
