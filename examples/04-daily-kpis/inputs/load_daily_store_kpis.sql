CREATE TEMP TABLE day_sales AS
SELECT storeId, COUNT(*) AS salesCount, SUM(amount) AS salesAmount
FROM retail.sales
WHERE DATE(soldAt) = @run_date
GROUP BY storeId;

CREATE TEMP TABLE day_returns AS
SELECT storeId, SUM(amount) AS returnsAmount
FROM retail.returns
WHERE DATE(returnedAt) = @run_date
GROUP BY storeId;

CREATE TEMP TABLE day_visits AS
SELECT storeId, COUNT(DISTINCT visitorId) AS visits
FROM retail.visits
WHERE DATE(visitedAt) = @run_date
GROUP BY storeId;

DELETE FROM retail.daily_store_kpis WHERE day = @run_date;

INSERT INTO retail.daily_store_kpis (day, storeId, revenue, visits, conversionRate)
SELECT
  @run_date AS day,
  st.storeId,
  COALESCE(s.salesAmount, 0) - COALESCE(r.returnsAmount, 0) AS revenue,
  COALESCE(v.visits, 0) AS visits,
  IF(COALESCE(v.visits, 0) = 0, 0, ROUND(COALESCE(s.salesCount, 0) / v.visits, 4)) AS conversionRate
FROM retail.stores AS st
LEFT JOIN day_sales AS s USING (storeId)
LEFT JOIN day_returns AS r USING (storeId)
LEFT JOIN day_visits AS v USING (storeId)
WHERE st.active;
