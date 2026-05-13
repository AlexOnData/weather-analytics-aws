-- Q1: Daily average temperature per city for the last 90 days.
SELECT
    date,
    city,
    ROUND(avg_temp, 1) AS avg_temperature,
    ROUND(min_temp, 1) AS min_temperature,
    ROUND(max_temp, 1) AS max_temperature
FROM daily_summary
WHERE date >= CURRENT_DATE - INTERVAL 90 DAY
ORDER BY city, date;
