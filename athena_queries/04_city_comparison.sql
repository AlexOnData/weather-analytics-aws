-- Q4: Pivot temperatures so each city is its own column.
SELECT
    date,
    MAX(CASE WHEN city = 'bucharest' THEN avg_temp END) AS bucharest_temp,
    MAX(CASE WHEN city = 'cluj'      THEN avg_temp END) AS cluj_temp,
    MAX(CASE WHEN city = 'constanta' THEN avg_temp END) AS constanta_temp,
    MAX(CASE WHEN city = 'timisoara' THEN avg_temp END) AS timisoara_temp
FROM daily_summary
WHERE date >= CURRENT_DATE - INTERVAL 365 DAY
GROUP BY date
ORDER BY date;
