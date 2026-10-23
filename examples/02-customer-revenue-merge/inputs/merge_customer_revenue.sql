MERGE sales.customer_revenue AS target
USING (
  SELECT c.customerId, c.country, SUM(o.amount) AS totalRevenue, MAX(o.orderDate) AS lastOrderDate
  FROM sales.orders AS o
  JOIN sales.customers AS c ON c.customerId = o.customerId
  WHERE o.status = 'PAID'
  GROUP BY c.customerId, c.country
) AS source
ON target.customerId = source.customerId
WHEN MATCHED THEN
  UPDATE SET country = source.country, totalRevenue = source.totalRevenue, lastOrderDate = source.lastOrderDate
WHEN NOT MATCHED THEN
  INSERT (customerId, country, totalRevenue, lastOrderDate)
  VALUES (source.customerId, source.country, source.totalRevenue, source.lastOrderDate);
