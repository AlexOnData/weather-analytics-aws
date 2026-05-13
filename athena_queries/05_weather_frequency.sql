-- Q5: How many days of each weather type per city this year (donut input).
SELECT
    city,
    dominant_weather AS weather_type,
    COUNT(*) AS days_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY city), 1) AS percentage
FROM daily_summary
WHERE year = EXTRACT(YEAR FROM CURRENT_DATE)
  AND dominant_weather IS NOT NULL
GROUP BY city, dominant_weather
ORDER BY city, days_count DESC;
