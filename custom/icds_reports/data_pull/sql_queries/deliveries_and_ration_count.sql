SELECT state_name,
       SUM(institutional_delivery_in_month) AS "# Institutional Deliveries",
       SUM(delivered_in_month)              AS "Total Deliveries",
       CASE
         WHEN SUM(delivered_in_month) > 0 THEN Trunc((
         SUM(institutional_delivery_in_month) / SUM(delivered_in_month) :: FLOAT
                                                 * 100
                                                     ) :: NUMERIC, 2)
         ELSE 0
       END                                  AS "% Institutional Deliveries",
       SUM(rations_21_plus_distributed)     AS
       "# PW and LM Given Take Home Ration for at Least 21 Days",
       SUM(thr_eligible)                    AS
       "Total PW and LM Eligible for Take Home Ration",
       CASE
         WHEN SUM(thr_eligible) > 0 THEN Trunc(
         ( SUM(rations_21_plus_distributed) / SUM(thr_eligible) :: FLOAT * 100 )
         ::
                                           NUMERIC, 2)
         ELSE 0
       END                                  AS
       "% THR (PW and LM, at Least 21 Days)"
FROM   agg_ccs_record_monthly
WHERE  aggregation_level = 1
       AND month = '{month}'
GROUP  BY state_name
