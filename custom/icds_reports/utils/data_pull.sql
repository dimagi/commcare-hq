SELECT COUNT(DISTINCT person_case_id) as girls_under_18 FROM "ccs_record_monthly" WHERE month='2020-05-01' AND alive_in_month=1 AND AND dob > '07-05-2002'::DATE AND dob <= '07-05-2009'::DATE;
-- QUERY PLAN
-- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Aggregate  (cost=0.00..0.00 rows=0 width=0)
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  Group  (cost=141648.45..141650.28 rows=367 width=37)
--                      Group Key: person_case_id
--                      ->  Sort  (cost=141648.45..141649.36 rows=367 width=37)
--                            Sort Key: person_case_id
--                            ->  Index Scan using crm_supervisor_person_month_idx_102712 on ccs_record_monthly_102712 ccs_record_monthly  (cost=0.56..141632.81 rows=367 width=37)
--                                  Index Cond: (month = '2020-05-01'::date)
--                                  Filter: ((dob > '2002-07-05'::date) AND (dob <= '2009-07-05'::date) AND (alive_in_month = 1))
-- (13 rows)                                 Filter: ((dob > '2002-07-05'::date) AND (alive_in_month = 1))


SELECT COUNT(DISTINCT person_case_id) as girls_under_15 FROM "ccs_record_monthly" WHERE month='2020-05-01' AND alive_in_month=1 AND dob > '07-05-2005'::DATE AND dob <= '07-05-2009'::DATE;

-- QUERY PLAN
-- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Aggregate  (cost=0.00..0.00 rows=0 width=0)
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  Group  (cost=141633.45..141633.59 rows=27 width=37)
--                      Group Key: person_case_id
--                      ->  Sort  (cost=141633.45..141633.52 rows=27 width=37)
--                            Sort Key: person_case_id
--                            ->  Index Scan using crm_supervisor_person_month_idx_102712 on ccs_record_monthly_102712 ccs_record_monthly  (cost=0.56..141632.81 rows=27 width=37)
--                                  Index Cond: (month = '2020-05-01'::date)
--                                  Filter: ((dob > '2005-07-05'::date) AND (dob <= '2009-07-05'::date) AND (alive_in_month = 1))
-- (13 rows)
