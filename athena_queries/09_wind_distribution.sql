-- Q9: Wind category distribution per city per season (polar/wind-rose input).
SELECT
    city,
    season,
    wind_category,
    COUNT(*) AS hours_count,
    ROUND(AVG(wind_speed_kmh), 1) AS avg_wind_speed,
    ROUND(MAX(wind_speed_kmh), 1) AS max_wind_speed
FROM weather_hourly
WHERE year >= EXTRACT(YEAR FROM CURRENT_DATE) - 1
  AND wind_category IS NOT NULL
GROUP BY city, season, wind_category
ORDER BY city, season, hours_count DESC;
