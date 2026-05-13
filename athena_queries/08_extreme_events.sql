-- Q8: Top 10 hottest, coldest, and rainiest days in the catalog.
SELECT * FROM (
    SELECT 'Hottest Day' AS category, city, date,
           CAST(max_temp AS VARCHAR) || '°C' AS value, max_temp AS sort_value
    FROM daily_summary
    ORDER BY max_temp DESC NULLS LAST
    LIMIT 10
)
UNION ALL
SELECT * FROM (
    SELECT 'Coldest Day' AS category, city, date,
           CAST(min_temp AS VARCHAR) || '°C' AS value, min_temp AS sort_value
    FROM daily_summary
    ORDER BY min_temp ASC NULLS LAST
    LIMIT 10
)
UNION ALL
SELECT * FROM (
    SELECT 'Rainiest Day' AS category, city, date,
           CAST(total_precipitation AS VARCHAR) || 'mm' AS value, total_precipitation AS sort_value
    FROM daily_summary
    ORDER BY total_precipitation DESC NULLS LAST
    LIMIT 10
)
ORDER BY category, sort_value DESC;
