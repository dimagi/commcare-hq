SELECT state_name,
       SUM(CASE
             WHEN age_tranche :: INTEGER <= 6 THEN valid_in_month
             ELSE 0
           END) AS "# Children (0-6m)",
       SUM(CASE
             WHEN age_tranche :: INTEGER BETWEEN 7 AND 36 THEN valid_in_month
             ELSE 0
           END) AS "# Children (6m-3y)",
       SUM(CASE
             WHEN age_tranche :: INTEGER > 36 THEN valid_in_month
             ELSE 0
           END) AS "# Children (3-6y)"
FROM   "agg_child_health_monthly"
WHERE  month = '{month}'
       AND aggregation_level = 1
GROUP  BY state_name
