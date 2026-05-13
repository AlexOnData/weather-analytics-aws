-- Q2: Monthly precipitation totals per city (last 2 years).
SELECT
    year,
    month,
    city,
    ROUND(SUM(total_precipitation), 1) AS monthly_precipitation_mm,
    COUNT(CASE WHEN total_precipitation > 0 THEN 1 END) AS rainy_days,
    ROUND(AVG(total_precipitation), 2) AS avg_daily_precipitation
FROM daily_summary
WHERE year >= EXTRACT(YEAR FROM CURRENT_DATE) - 2
GROUP BY year, month, city
ORDER BY city, year, month;
