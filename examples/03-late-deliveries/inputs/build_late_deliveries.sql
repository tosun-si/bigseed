DELETE FROM logistics.late_deliveries WHERE TRUE;

INSERT INTO logistics.late_deliveries (orderId, promisedDate, delayDays)
SELECT orderId, promisedDate, DATE_DIFF(deliveredDate, promisedDate, DAY) AS delayDays
FROM logistics.shipments
WHERE status != 'CANCELLED'
  AND deliveredDate IS NOT NULL
  AND DATE_DIFF(deliveredDate, promisedDate, DAY) >= 2;
