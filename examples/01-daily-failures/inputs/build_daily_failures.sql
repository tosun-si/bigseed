DELETE FROM monitoring.daily_failures WHERE TRUE;

INSERT INTO monitoring.daily_failures (day, featureName, failuresCount)
SELECT DATE(dwhCreationDate) AS day, featureName, COUNT(*) AS failuresCount
FROM monitoring.job_failure
WHERE featureName IS NOT NULL
GROUP BY day, featureName
HAVING COUNT(*) >= 2;
