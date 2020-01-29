SELECT
    state_name,
    district_name,
    SUM(num_launched_awcs),
    SUM(CASE WHEN awc_days_open/31.0 *100 < 60 THEN 1 ELSE 0 END) AS "Num AWCs open on less that 60% of days",
    SUM(CASE WHEN wer_eligible > 0 THEN
             CASE WHEN(wer_weighed/wer_eligible::float)*100<60 THEN 1 ELSE 0 END
        ELSE 0
        END
    ) AS "Num AWCs with less than 60% Weighing efficiency",
    SUM(CASE WHEN contact_phone_number IS NULL OR contact_phone_number!='' THEN 1 ELSE 0 END) AS "Num AWWs without phone number",
    SUM(CASE WHEN num_awc_infra_last_update<>1 THEN 1 ELSE 0 END ) AS "Num AWCs that havent submitted infra form in last 6 months",
    count(*) FILTER (WHERE infra_clean_water=0 OR infra_clean_water IS NULL) AS "Num AWCs that with no drinking water",
    count(*) FILTER (WHERE infra_functional_toilet=0 OR infra_functional_toilet IS NULL) AS "Num AWCs that with no functional toilet",
    count(*) FILTER (WHERE infantometer=0 OR infantometer IS NULL) AS "Num AWCs that with no infantometer",
    count(*) FILTER (WHERE stadiometer=0 OR stadiometer IS NULL) AS "Num AWCs that with no stadiometer",
    count(*) FILTER (WHERE infra_medicine_kits=0 OR infra_medicine_kits IS NULL) AS "Num AWCs that with no meidicine kit",
    count(*) FILTER (WHERE infra_infant_weighing_scale=0 OR infra_infant_weighing_scale IS NULL) AS "Num AWCs that with no baby scale",
    count(*) FILTER (WHERE infra_adult_weighing_scale=0 OR infra_adult_weighing_scale IS NULL) AS "Num AWCs that with no adult scale",
    count(*) FILTER (WHERE electricity_awc=0 OR electricity_awc IS NULL) AS "Num AWCs that with no electricty"
FROM agg_awc_monthly WHERE month='2019-12-01' AND aggregation_level=5 AND state_is_test<>1
GROUP BY state_name, district_name;

/*
GroupAggregate  (cost=187235.58..187236.16 rows=6 width=123)
   Group Key: awc_location.state_name, awc_location.district_name
   ->  Sort  (cost=187235.58..187235.59 rows=6 width=83)
         Sort Key: awc_location.state_name, awc_location.district_name
         ->  Nested Loop  (cost=1000.00..187235.50 rows=6 width=83)
               ->  Gather  (cost=1000.00..187210.44 rows=1 width=87)
                     Workers Planned: 4
                     ->  Nested Loop  (cost=0.00..186210.34 rows=1 width=87)
                           ->  Parallel Seq Scan on awc_location_local awc_location  (cost=0.00..71121.43 rows=181398 width=195)
                                 Filter: (aggregation_level = 5)
                           ->  Append  (cost=0.00..0.61 rows=2 width=225)
                                 ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=220)
                                       Filter: ((state_is_test <> 1) AND (month = '2019-12-01'::date) AND (aggregation_level = 5) AND (awc_location.state_id = state_id) AND (awc_location.district_id = district_id) AND (awc_location.block_id = block_id) AND (awc_location.supervisor_id = supervisor_id) AND (awc_location.doc_id = awc_id))
                                 ->  Index Scan using "agg_awc_2019-12-01_5_awc_id_idx" on "agg_awc_2019-12-01_5" agg_awc_1  (cost=0.42..0.60 rows=1 width=225)
                                       Index Cond: (awc_id = awc_location.doc_id)
                                       Filter: ((state_is_test <> 1) AND (month = '2019-12-01'::date) AND (aggregation_level = 5) AND (awc_location.state_id = state_id) AND (awc_location.district_id = district_id) AND (awc_location.block_id = block_id) AND (awc_location.supervisor_id = supervisor_id))
               ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                     Filter: (start_date = '2019-12-01'::date)
*/

# find just launched awcs in last month to evaluate AWCS launched in original month only
SELECT
    state_name,
    district_name,
    SUM(num_launched_awcs)
FROM agg_awc_monthly WHERE month='2019-11-01' AND aggregation_level=2 AND state_is_test<>1
GROUP BY state_name, district_name

/*
GroupAggregate  (cost=276.44..276.56 rows=6 width=27)
   Group Key: awc_location.state_name, awc_location.district_name
   ->  Sort  (cost=276.44..276.46 rows=6 width=23)
         Sort Key: awc_location.state_name, awc_location.district_name
         ->  Nested Loop  (cost=197.57..276.37 rows=6 width=23)
               ->  Hash Join  (cost=197.57..251.31 rows=1 width=27)
                     Hash Cond: ((agg_awc.state_id = awc_location.state_id) AND (agg_awc.district_id = awc_location.district_id) AND (agg_awc.block_id = awc_location.block_id) AND (agg_awc.supervisor_id = awc_location.supervisor_id) AND (agg_awc.awc_id = awc_location.doc_id))
                     ->  Append  (cost=0.00..48.70 rows=383 width=90)
                           ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=172)
                                 Filter: ((state_is_test <> 1) AND (month = '2019-11-01'::date) AND (aggregation_level = 2))
                           ->  Seq Scan on "agg_awc_2019-11-01_2" agg_awc_1  (cost=0.00..46.79 rows=382 width=90)
                                 Filter: ((state_is_test <> 1) AND (month = '2019-11-01'::date) AND (aggregation_level = 2))
                     ->  Hash  (cost=188.48..188.48 rows=404 width=183)
                           ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc_location  (cost=0.42..188.48 rows=404 width=183)
                                 Index Cond: (aggregation_level = 2)
               ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                     Filter: (start_date = '2019-11-01'::date)
*/


