SELECT
    awc.awc_name,
    awc.awc_site_code,
    awc.supervisor_name,
    awc.supervisor_site_code,
    awc.block_name,
    awc.block_site_code,
    awc.district_name,
    awc.district_site_code,
    awc.state_name,
    awc.state_site_code,
    ucr.count
    FROM "awc_location" awc LEFT JOIN
    "ucr_icds-cas_static-awc_mgt_forms_ad1b11f0" ucr ON (
        awc.doc_id = ucr.awc_id
    )

    WHERE awc.aggregation_level=5 and submitted_on >= '2020-01-01' AND
                  submitted_on < '2020-03-01';


--                                                           QUERY PLAN
-- -------------------------------------------------------------------------------------------------------------------------------
--  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--    Task Count: 64
--    Tasks Shown: One of 64
--    ->  Task
--          Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--          ->  Nested Loop  (cost=0.55..14251.71 rows=5825 width=117)
--                ->  Seq Scan on "ucr_icds-cas_static-awc_mgt_forms_ad1b11f0_103162" ucr  (cost=0.00..948.19 rows=5064 width=37)
--                      Filter: ((submitted_on >= '2020-01-01'::date) AND (submitted_on < '2020-03-01'::date))
--                ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc  (cost=0.55..2.62 rows=1 width=144)
--                      Index Cond: (doc_id = ucr.awc_id)
--                      Filter: (aggregation_level = 5)
-- (11 rows)
