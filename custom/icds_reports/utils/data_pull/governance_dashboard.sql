-- to pull the vhnd data submitted in November
SELECT
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    '2019-11-01' as month,
    1 as vhsnd_conducted,
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



select
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    SUM(CASE WHEN age_tranche::INTEGER<=36 THEN valid_in_month else 0 END) as open_valid_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 THEN valid_in_month else 0 END) as open_valid_till_month_3_6,
    SUM(CASE WHEN age_tranche::INTEGER<=36 THEN valid_all_registered_in_month else 0 END) as open_register_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 THEN valid_all_registered_in_month else 0 END) as open_register_till_month_3_6
FROM agg_awc_monthly
    left join agg_child_health  on
    agg_awc_monthly.awc_id= agg_child_health.awc_id and
    agg_awc_monthly.month=agg_child_health.month and
    agg_awc_monthly.aggregation_level=agg_child_health.aggregation_level
where agg_awc_monthly.num_launched_awcs=1 and agg_awc_monthly.month='2019-11-01' and agg_awc_monthly.aggregation_level=5
group by state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name

/*
 GroupAggregate  (cost=1514843.35..1514845.27 rows=24 width=108)
   Group Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name
   ->  Sort  (cost=1514843.35..1514843.41 rows=24 width=86)
         Sort Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name
         ->  Nested Loop Left Join  (cost=80296.62..1514842.80 rows=24 width=86)
               Join Filter: ((months.start_date = agg_child_health.month) AND (months.start_date = agg_child_health.month))
               ->  Nested Loop  (cost=80296.62..208072.31 rows=1 width=115)
                     ->  Gather  (cost=80296.62..208047.25 rows=1 width=115)
                           Workers Planned: 4
                           ->  Parallel Hash Join  (cost=79296.62..207047.15 rows=1 width=115)
                                 Hash Cond: ((agg_awc_1.state_id = awc_location.state_id) AND (agg_awc_1.district_id = awc_location.district_id) AND (agg_awc_1.block_id = awc_location.block_id) AND (agg_awc_1.supervisor_id = awc_location.supervisor_id) AND (agg_awc_1.awc_id = awc_location.doc_id))
                                 ->  Parallel Append  (cost=0.00..113228.11 rows=141670 width=173)
                                       ->  Parallel Seq Scan on "agg_awc_2019-11-01_5" agg_awc_1  (cost=0.00..112519.76 rows=141670 width=173)
                                             Filter: ((month = '2019-11-01'::date) AND (aggregation_level = 5) AND (num_launched_awcs = 1))
                                       ->  Parallel Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=168)
                                             Filter: ((month = '2019-11-01'::date) AND (aggregation_level = 5) AND (num_launched_awcs = 1))
                                 ->  Parallel Hash  (cost=69540.88..69540.88 rows=178255 width=240)
                                       ->  Parallel Seq Scan on awc_location_local awc_location  (cost=0.00..69540.88 rows=178255 width=240)
                                             Filter: (aggregation_level = 5)
                     ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                           Filter: (start_date = '2019-11-01'::date)
               ->  Append  (cost=0.00..1306770.38 rows=8 width=50)
                     ->  Seq Scan on agg_child_health  (cost=0.00..0.00 rows=1 width=80)
                           Filter: ((month = '2019-11-01'::date) AND (aggregation_level = 5) AND (awc_location.aggregation_level = aggregation_level) AND (awc_location.doc_id = awc_id))
                     ->  Index Scan using staging_agg_child_health_aggregation_level_gender_idx1 on "agg_child_health_2019-11-01"  (cost=0.56..1306770.34 rows=7 width=50)
                           Index Cond: ((awc_location.aggregation_level = aggregation_level) AND (aggregation_level = 5))
                           Filter: ((month = '2019-11-01'::date) AND (awc_location.doc_id = awc_id))
(27 rows)

*/

select
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    SUM(CASE WHEN age_tranche::INTEGER<=36 THEN valid_in_month else 0 END) as open_valid_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 THEN valid_in_month else 0 END) as open_valid_till_month_3_6,
    SUM(CASE WHEN age_tranche::INTEGER<=36 THEN valid_all_registered_in_month else 0 END) as open_register_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 THEN valid_all_registered_in_month else 0 END) as open_register_till_month_3_6
FROM agg_awc_monthly
    left join agg_child_health  on
    agg_awc_monthly.awc_id= agg_child_health.awc_id and
    agg_awc_monthly.month=agg_child_health.month and agg_awc_monthly.month=agg_child_health.month and
    agg_awc_monthly.aggregation_level=agg_child_health.aggregation_level
where agg_awc_monthly.num_launched_awcs=1 and agg_awc_monthly.month='2019-10-01' and agg_awc_monthly.aggregation_level=5
group by state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name

/*
 GroupAggregate  (cost=1385741.00..1385742.76 rows=22 width=108)
   Group Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name
   ->  Sort  (cost=1385741.00..1385741.05 rows=22 width=86)
         Sort Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name
         ->  Nested Loop Left Join  (cost=80296.62..1385740.51 rows=22 width=86)
               Join Filter: ((months.start_date = agg_child_health.month) AND (months.start_date = agg_child_health.month))
               ->  Nested Loop  (cost=80296.62..201384.21 rows=1 width=115)
                     ->  Gather  (cost=80296.62..201359.15 rows=1 width=115)
                           Workers Planned: 4
                           ->  Parallel Hash Join  (cost=79296.62..200359.05 rows=1 width=115)
                                 Hash Cond: ((agg_awc_1.state_id = awc_location.state_id) AND (agg_awc_1.district_id = awc_location.district_id) AND (agg_awc_1.block_id = awc_location.block_id) AND (agg_awc_1.supervisor_id = awc_location.supervisor_id) AND (agg_awc_1.awc_id = awc_location.doc_id))
                                 ->  Parallel Append  (cost=0.00..107009.76 rows=134070 width=173)
                                       ->  Parallel Seq Scan on "agg_awc_2019-10-01_5" agg_awc_1  (cost=0.00..106339.41 rows=134070 width=173)
                                             Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 5) AND (num_launched_awcs = 1))
                                       ->  Parallel Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=168)
                                             Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 5) AND (num_launched_awcs = 1))
                                 ->  Parallel Hash  (cost=69540.88..69540.88 rows=178255 width=240)
                                       ->  Parallel Seq Scan on awc_location_local awc_location  (cost=0.00..69540.88 rows=178255 width=240)
                                             Filter: (aggregation_level = 5)
                     ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                           Filter: (start_date = '2019-10-01'::date)
               ->  Append  (cost=0.00..1184356.18 rows=8 width=50)
                     ->  Seq Scan on agg_child_health  (cost=0.00..0.00 rows=1 width=80)
                           Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 5) AND (awc_location.aggregation_level = aggregation_level) AND (awc_location.doc_id = awc_id))
                     ->  Index Scan using staging_agg_child_health_aggregation_level_gender_idx2 on "agg_child_health_2019-10-01"  (cost=0.43..1184356.14 rows=7 width=50)
                           Index Cond: ((awc_location.aggregation_level = aggregation_level) AND (aggregation_level = 5))
                           Filter: ((month = '2019-10-01'::date) AND (awc_location.doc_id = awc_id))
(27 rows)
*/




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
