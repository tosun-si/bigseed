# Customer revenue

The table `sales.customer_revenue` keeps the revenue of each customer, refreshed by `merge_customer_revenue.sql`.

- R1: only the orders with the status PAID count in the revenue (REFUNDED and CANCELLED orders don't).
- R2: an order of a customer missing from `sales.customers` is ignored.
- R3: a customer already in `sales.customer_revenue` gets its total revenue and its last order date replaced by the
  new values, and its country refreshed from `sales.customers`.
- R4: a customer with paid orders and not yet in `sales.customer_revenue` is inserted.
- R5: a customer already in `sales.customer_revenue` without any paid order keeps its row unchanged.
