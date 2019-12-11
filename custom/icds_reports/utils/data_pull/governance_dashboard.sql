-- to pull the vhnd data submitted in November
SELECT
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    '2019-11-01' as month,
    case when ucr.submitted_on is not null THEN 'yes' ELSE 'no' as vhsnd_conducted,
    vhsnd_date_past_month,
    child_immu,
    anc_today,
    vhnd_gmp
FROM agg_awc_monthly full join "ucr_icds-cas_static-vhnd_form_28e7fd58" ucr
    ON (ucr.awc_id = agg_awc_monthly.awc_id and ucr.vhsnd_date_past_month>='2019-11-01' and ucr.vhsnd_date_past_month<'2019-12-01')
where agg_awc_monthly.num_launched_awcs=1 and agg_awc_monthly.month='2019-11-01' and agg_awc_monthly.aggregation_level=5;


/*
 Nested Loop  (cost=1000.85..203493.44 rows=6 width=128)
   ->  Nested Loop Left Join  (cost=1000.85..203468.38 rows=1 width=96)
         ->  Gather  (cost=1000.42..203467.54 rows=1 width=111)
               Workers Planned: 4
               ->  Nested Loop  (cost=0.42..202467.44 rows=1 width=111)
                     ->  Parallel Append  (cost=0.00..113228.11 rows=141670 width=173)
                           ->  Parallel Seq Scan on "agg_awc_2019-11-01_5" agg_awc_1  (cost=0.00..112519.76 rows=141670 width=173)
                                 Filter: ((month = '2019-11-01'::date) AND (aggregation_level = 5) AND (num_launched_awcs = 1))
                           ->  Parallel Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=168)
                                 Filter: ((month = '2019-11-01'::date) AND (aggregation_level = 5) AND (num_launched_awcs = 1))
                     ->  Index Scan using awc_location_local_doc_id_idx on awc_location_local awc_location  (cost=0.42..0.62 rows=1 width=240)
                           Index Cond: (doc_id = agg_awc_1.awc_id)
                           Filter: ((aggregation_level = 5) AND (agg_awc_1.state_id = state_id) AND (agg_awc_1.district_id = district_id) AND (agg_awc_1.block_id = block_id) AND (agg_awc_1.supervisor_id = supervisor_id))
         ->  Index Scan using "ix_ucr_icds-cas_static-vhnd_form_28e7fd58_awc_id" on "ucr_icds-cas_static-vhnd_form_28e7fd58" ucr  (cost=0.43..0.84 rows=1 width=49)
               Index Cond: (awc_id = awc_location.doc_id)
               Filter: ((vhsnd_date_past_month >= '2019-11-01'::date) AND (vhsnd_date_past_month < '2019-12-01'::date))
   ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
         Filter: (start_date = '2019-11-01'::date)
(18 rows)

*/



create unlogged table temp_child_data_pull as select
awc_id,
    SUM(CASE WHEN age_tranche::INTEGER<=36 THEN valid_in_month else 0 END) as open_valid_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 THEN valid_in_month else 0 END) as open_valid_till_month_3_6,
    SUM(CASE WHEN age_tranche::INTEGER<=36 THEN valid_all_registered_in_month else 0 END) as open_register_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 THEN valid_all_registered_in_month else 0 END) as open_register_till_month_3_6
from "child_health_monthly" child_health where month='2019-10-01'
group by awc_id;
/*
 HashAggregate  (cost=0.00..0.00 rows=0 width=0)
   Group Key: remote_scan.awc_id
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 64
         Tasks Shown: One of 64
         ->  Task
               Node: host=100.71.184.232 port=6432 dbname=icds_ucr
               ->  Finalize GroupAggregate  (cost=463779.67..469225.78 rows=8043 width=65)
                     Group Key: awc_id
                     ->  Gather Merge  (cost=463779.67..468642.66 rows=40215 width=65)
                           Workers Planned: 5
                           ->  Sort  (cost=462779.59..462799.70 rows=8043 width=65)
                                 Sort Key: awc_id
                                 ->  Partial HashAggregate  (cost=462177.43..462257.86 rows=8043 width=65)
                                       Group Key: awc_id
                                       ->  Parallel Index Scan using chm_month_supervisor_id_102648 on child_health_monthly_102648 child_health  (cost=0.56..454458.92 rows=134235 width=43)
                                             Index Cond: (month = '2019-10-01'::date)
(17 rows)
 */


COPY(select
state_name,
district_name,
block_name,
supervisor_name,
awc_name
sum(open_valid_till_month_0_3) as "open_valid_till_month_0_3",
sum(open_valid_till_month_3_6) as "open_valid_till_month_3_6",
sum(open_register_till_month_0_3) as "open_register_till_month_0_3",
sum(open_register_till_month_3_6)as "open_register_till_month_3_6",
from temp_child_data_pull t join awc_location_local a on a.doc_id=t.awc_id where aggregation_level=5 and state_is_test=0
group by state_name,
district_name,
block_name,
supervisor_name,
awc_name
order by state_name asc) to 'child_Oct.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';










-- to get pw and lw data for nov and Oct in one sheet
select
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    cases_ccs_pregnant_all as open_pw_registered_till_month,
    cases_ccs_lactating_all as open_lw_registered_till_month,
    cases_ccs_lactating as open_lw_valid_till_month,
    cases_ccs_pregnant as open_lw_valid_till_month,
FROM agg_awc_monthly
where agg_awc_monthly.num_launched_awcs=1 and agg_awc_monthly.month='2019-11-01' and agg_awc_monthly.aggregation_level=5
/*
 Nested Loop  (cost=1000.42..203492.60 rows=6 width=92)
   ->  Gather  (cost=1000.42..203467.54 rows=1 width=96)
         Workers Planned: 4
         ->  Nested Loop  (cost=0.42..202467.44 rows=1 width=96)
               ->  Parallel Append  (cost=0.00..113228.11 rows=141670 width=189)
                     ->  Parallel Seq Scan on "agg_awc_2019-11-01_5" agg_awc_1  (cost=0.00..112519.76 rows=141670 width=189)
                           Filter: ((month = '2019-11-01'::date) AND (aggregation_level = 5) AND (num_launched_awcs = 1))
                     ->  Parallel Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=184)
                           Filter: ((month = '2019-11-01'::date) AND (aggregation_level = 5) AND (num_launched_awcs = 1))
               ->  Index Scan using awc_location_local_doc_id_idx on awc_location_local awc_location  (cost=0.42..0.62 rows=1 width=240)
                     Index Cond: (doc_id = agg_awc_1.awc_id)
                     Filter: ((aggregation_level = 5) AND (agg_awc_1.state_id = state_id) AND (agg_awc_1.district_id = district_id) AND (agg_awc_1.block_id = block_id) AND (agg_awc_1.supervisor_id = supervisor_id))
   ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
         Filter: (start_date = '2019-11-01'::date)
(14 rows)
 */


select
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    cases_ccs_pregnant_all as open_pw_registered_till_month,
    cases_ccs_lactating_all as open_lw_registered_till_month,
    cases_ccs_lactating as open_lw_valid_till_month,
    cases_ccs_pregnant as open_lw_valid_till_month,
FROM agg_awc_monthly
where agg_awc_monthly.num_launched_awcs=1 and agg_awc_monthly.month='2019-10-01' and agg_awc_monthly.aggregation_level=5
/*
 Nested Loop  (cost=1000.42..203492.60 rows=6 width=92)
   ->  Gather  (cost=1000.42..203467.54 rows=1 width=96)
         Workers Planned: 4
         ->  Nested Loop  (cost=0.42..202467.44 rows=1 width=96)
               ->  Parallel Append  (cost=0.00..113228.11 rows=141670 width=189)
                     ->  Parallel Seq Scan on "agg_awc_2019-11-01_5" agg_awc_1  (cost=0.00..112519.76 rows=141670 width=189)
                           Filter: ((month = '2019-11-01'::date) AND (aggregation_level = 5) AND (num_launched_awcs = 1))
                     ->  Parallel Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=184)
                           Filter: ((month = '2019-11-01'::date) AND (aggregation_level = 5) AND (num_launched_awcs = 1))
               ->  Index Scan using awc_location_local_doc_id_idx on awc_location_local awc_location  (cost=0.42..0.62 rows=1 width=240)
                     Index Cond: (doc_id = agg_awc_1.awc_id)
                     Filter: ((aggregation_level = 5) AND (agg_awc_1.state_id = state_id) AND (agg_awc_1.district_id = district_id) AND (agg_awc_1.block_id = block_id) AND (agg_awc_1.supervisor_id = supervisor_id))
   ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
         Filter: (start_date = '2019-11-01'::date)
(14 rows)
 */









​
