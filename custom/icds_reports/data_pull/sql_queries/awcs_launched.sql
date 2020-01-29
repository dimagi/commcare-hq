SELECT state_name,
       num_awcs               AS "Total AWCs",
       num_launched_awcs      AS "AWCs Launched",
       num_launched_districts AS "Districts launched",
       awc_days_open,
       CASE
         WHEN num_launched_awcs > 0 THEN awc_days_open / num_launched_awcs
         ELSE awc_days_open
       END                    AS "Avg. # of Days AWCs open"
FROM   agg_awc_monthly
WHERE  aggregation_level = 1
       AND month = '{month}'
