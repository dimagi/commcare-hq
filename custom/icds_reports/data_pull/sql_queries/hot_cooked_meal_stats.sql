SELECT state_name,
       total_thr_candidates AS
       "Total Beneficiaries (PW, LM & Children 6-36m) Eligible for THR",
       thr_given_21_days    AS
       "#Beneficiaries (PW, LM & Children 6-36m) Given THR >=21 Days",
       CASE
         WHEN total_thr_candidates > 0 THEN Trunc((
         thr_given_21_days / total_thr_candidates :: FLOAT * 100 ) :: NUMERIC, 2
                                            )
         ELSE 0
       END                  AS
       "% THR (PW, LM and Children 6-36m, at Least 21 Days)",
       pse_attended_21_days AS "# Children (3-6y) who Attended PSE  >= 21 Days",
       children_3_6         AS "Total Children (3-6y) Eligible to Attend PSE",
       CASE
         WHEN children_3_6 > 0 THEN Trunc(( pse_attended_21_days / children_3_6
                                            ::
                                            FLOAT * 100 ) :: NUMERIC, 2)
         ELSE 0
       END                  AS "% PSE (3-6y, at Least 21 Days)",
       lunch_count_21_days  AS
       "# Children (3-6y) Given Hot Cooked Meal for >=21 Days",
       children_3_6         AS
       "Total Children (3-6y) Eligible for Hot Cooked Meal",
       CASE
         WHEN children_3_6 > 0 THEN Trunc(( lunch_count_21_days / children_3_6
                                            :: FLOAT
                                            * 100 ) :: NUMERIC, 2)
         ELSE 0
       END                  AS "% HCM (3-6y, at Least 21 Days)",
       expected_visits      AS "Total Expected Home Visits",
       valid_visits         AS "# Home Visits Done",
       CASE
         WHEN expected_visits > 0 THEN Trunc((
         valid_visits / expected_visits :: FLOAT
         * 100 ) :: NUMERIC, 2)
         ELSE 0
       END                  AS "% HVs"
FROM   service_delivery_monthly
WHERE  aggregation_level = 1
       AND month = '{month}'
