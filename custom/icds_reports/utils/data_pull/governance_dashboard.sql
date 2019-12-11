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



-- to get children open and valid in oct and Nov in single query. It is needed in single query because they are needed in a single sheet for manipulation
select
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    SUM(CASE WHEN agg1.age_tranche::INTEGER<=36 THEN agg1.valid_in_month else 0 END) as open_valid_till_month_0_3_Nov,
    SUM(CASE WHEN agg1.age_tranche::INTEGER between 37 and 72 THEN agg1.valid_in_month else 0 END) as open_valid_till_month_3_6_Nov,
    SUM(CASE WHEN agg1.age_tranche::INTEGER<=36 THEN agg1.valid_all_registered_in_month else 0 END) as open_register_till_month_0_3_Nov,
    SUM(CASE WHEN agg1.age_tranche::INTEGER between 37 and 72 THEN agg1.valid_all_registered_in_month else 0 END) as open_register_till_month_3_6_Nov,

    SUM(CASE WHEN agg2.age_tranche::INTEGER<=36 THEN agg2.valid_in_month else 0 END) as open_valid_till_month_0_3_Oct,
    SUM(CASE WHEN agg2.age_tranche::INTEGER between 37 and 72 THEN agg2.valid_in_month else 0 END) as open_valid_till_month_3_6_Oct,
    SUM(CASE WHEN agg2.age_tranche::INTEGER<=36 THEN agg2.valid_all_registered_in_month else 0 END) as open_register_till_month_0_3_Oct,
    SUM(CASE WHEN agg2.age_tranche::INTEGER between 37 and 72 THEN agg2.valid_all_registered_in_month else 0 END) as open_register_till_month_3_6_Oct
FROM agg_awc_monthly
left join (select * from agg_child_health where aggregation_level=5 and month='2019-11-01') agg1
    on agg_awc_monthly.awc_id= agg1.awc_id and
       agg_awc_monthly.month=agg1.month and
       agg_awc_monthly.aggregation_level=agg1.aggregation_level

left join (select * from agg_child_health where aggregation_level=5 and month='2019-10-01') agg2
    on agg_awc_monthly.awc_id= agg2.awc_id and
       agg_awc_monthly.month=agg2.month and
       agg_awc_monthly.aggregation_level=agg2.aggregation_level

where agg_awc_monthly.num_launched_awcs=1 and agg_awc_monthly.month='2019-11-01' and agg_awc_monthly.aggregation_level=5
group by state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name
/*
 GroupAggregate  (cost=1982705.03..1982705.17 rows=1 width=140)
   Group Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name
   ->  Sort  (cost=1982705.03..1982705.04 rows=1 width=86)
         Sort Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name
         ->  Nested Loop Left Join  (cost=80715.85..1982705.02 rows=1 width=86)
               Join Filter: ((months.start_date = month) AND (awc_location.doc_id = awc_id) AND (awc_location.aggregation_level = aggregation_level))
               ->  Nested Loop Left Join  (cost=80715.85..1982705.01 rows=1 width=125)
                     Join Filter: (months.start_date = agg_child_health.month)
                     ->  Nested Loop  (cost=80715.85..210666.84 rows=1 width=115)
                           ->  Gather  (cost=80715.85..210641.78 rows=1 width=115)
                                 Workers Planned: 4
                                 ->  Parallel Hash Join  (cost=79715.85..209641.68 rows=1 width=115)
                                       Hash Cond: ((agg_awc_5.aggregation_level = awc_location.aggregation_level) AND (agg_awc_5.state_id = awc_location.state_id) AND (agg_awc_5.district_id = awc_location.district_id) AND (agg_awc_5.block_id = awc_location.block_id) AND (agg_awc_5.supervisor_id = awc_location.supervisor_id) AND (agg_awc_5.awc_id = awc_location.doc_id))
                                       ->  Parallel Append  (cost=0.00..114779.23 rows=141752 width=173)
                                             ->  Parallel Seq Scan on "agg_awc_2019-11-01_5" agg_awc_5  (cost=0.00..112074.08 rows=141670 width=173)
                                                   Filter: ((month = '2019-11-01'::date) AND (num_launched_awcs = 1))
                                             ->  Parallel Seq Scan on "agg_awc_2019-11-01_4" agg_awc_4  (cost=0.00..1716.89 rows=185 width=144)
                                                   Filter: ((month = '2019-11-01'::date) AND (num_launched_awcs = 1))
                                             ->  Parallel Seq Scan on "agg_awc_2019-11-01_3" agg_awc_3  (cost=0.00..253.78 rows=7 width=115)
                                                   Filter: ((month = '2019-11-01'::date) AND (num_launched_awcs = 1))
                                             ->  Parallel Seq Scan on "agg_awc_2019-11-01_2" agg_awc_2  (cost=0.00..23.42 rows=1 width=86)
                                                   Filter: ((month = '2019-11-01'::date) AND (num_launched_awcs = 1))
                                             ->  Parallel Seq Scan on "agg_awc_2019-11-01_1" agg_awc_1  (cost=0.00..2.30 rows=1 width=168)
                                                   Filter: ((month = '2019-11-01'::date) AND (num_launched_awcs = 1))
                                             ->  Parallel Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=168)
                                                   Filter: ((month = '2019-11-01'::date) AND (num_launched_awcs = 1))
                                       ->  Parallel Hash  (cost=69076.10..69076.10 rows=185910 width=240)
                                             ->  Parallel Seq Scan on awc_location_local awc_location  (cost=0.00..69076.10 rows=185910 width=240)
                           ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                                 Filter: (start_date = '2019-11-01'::date)
                     ->  Append  (cost=0.00..1772038.06 rows=8 width=50)
                           ->  Seq Scan on agg_child_health  (cost=0.00..0.00 rows=1 width=80)
                                 Filter: ((aggregation_level = 5) AND (month = '2019-11-01'::date) AND (awc_location.doc_id = awc_id) AND (awc_location.aggregation_level = aggregation_level))
                           ->  Index Scan using staging_agg_child_health_aggregation_level_gender_idx1 on "agg_child_health_2019-11-01"  (cost=0.56..1772038.02 rows=7 width=50)
                                 Index Cond: ((awc_location.aggregation_level = aggregation_level) AND (aggregation_level = 5))
                                 Filter: ((month = '2019-11-01'::date) AND (awc_location.doc_id = awc_id))
               ->  Result  (cost=0.00..0.00 rows=0 width=0)
                     One-Time Filter: false
(38 rows)

*/



-- to get pw and lw data for nov and Oct in one sheet
select
    agg1.state_name,
    agg1.district_name,
    agg1.block_name,
    agg1.supervisor_name,
    agg1.awc_name,
    agg1.cases_ccs_pregnant_all as open_pw_registered_till_month_Nov,
    agg1.cases_ccs_lactating_all as open_lw_registered_till_month_Nov,
    agg1.cases_ccs_lactating as open_lw_valid_till_month_Nov,
    agg1.cases_ccs_pregnant as open_lw_valid_till_month_Nov,

    agg2.cases_ccs_pregnant_all as open_pw_registered_till_month_Oct,
    agg2.cases_ccs_lactating_all as open_lw_registered_till_month_Oct,
    agg2.cases_ccs_lactating as open_lw_valid_till_month_Oct,
    agg2.cases_ccs_pregnant as open_lw_valid_till_month_Oct

FROM (select * from agg_awc_monthly where  month='2019-11-01' and aggregation_level=5) agg1
    left join (select * from agg_awc_monthly where  month='2019-10-01' and aggregation_level=5) agg2
    on agg1.awc_id = agg2.awc_id and
    agg1.aggregation_level=agg2.aggregation_level

where agg1.num_launched_awcs=1

/*
 Nested Loop  (cost=1000.85..203523.10 rows=6 width=108)
   ->  Nested Loop Left Join  (cost=1000.85..203498.04 rows=1 width=112)
         ->  Gather  (cost=1000.42..203467.54 rows=1 width=131)
               Workers Planned: 4
               ->  Nested Loop  (cost=0.42..202467.44 rows=1 width=131)
                     ->  Parallel Append  (cost=0.00..113228.11 rows=141670 width=189)
                           ->  Parallel Seq Scan on "agg_awc_2019-11-01_5" agg_awc_1  (cost=0.00..112519.76 rows=141670 width=189)
                                 Filter: ((month = '2019-11-01'::date) AND (aggregation_level = 5) AND (num_launched_awcs = 1))
                           ->  Parallel Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=184)
                                 Filter: ((month = '2019-11-01'::date) AND (aggregation_level = 5) AND (num_launched_awcs = 1))
                     ->  Index Scan using awc_location_local_doc_id_idx on awc_location_local awc_location  (cost=0.42..0.62 rows=1 width=240)
                           Index Cond: (doc_id = agg_awc_1.awc_id)
                           Filter: ((aggregation_level = 5) AND (agg_awc_1.state_id = state_id) AND (agg_awc_1.district_id = district_id) AND (agg_awc_1.block_id = block_id) AND (agg_awc_1.supervisor_id = supervisor_id))
         ->  Nested Loop Left Join  (cost=0.42..30.44 rows=6 width=51)
               Join Filter: (months_1.start_date = agg_awc_2.month)
               ->  Nested Loop  (cost=0.42..25.64 rows=6 width=168)
                     ->  Index Scan using awc_location_local_doc_id_idx on awc_location_local awc_location_1  (cost=0.42..0.58 rows=1 width=164)
                           Index Cond: (awc_location.doc_id = doc_id)
                           Filter: ((aggregation_level = 5) AND (awc_location.aggregation_level = aggregation_level))
                     ->  Seq Scan on icds_months_local months_1  (cost=0.00..25.00 rows=6 width=4)
                           Filter: (start_date = '2019-10-01'::date)
               ->  Append  (cost=0.00..0.78 rows=2 width=189)
                     ->  Seq Scan on agg_awc agg_awc_2  (cost=0.00..0.00 rows=1 width=184)
                           Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 5) AND (awc_location_1.aggregation_level = aggregation_level) AND (awc_location_1.state_id = state_id) AND (awc_location_1.district_id = district_id) AND (awc_location_1.block_id = block_id) AND (awc_location_1.supervisor_id = supervisor_id) AND (awc_location_1.doc_id = awc_id))
                     ->  Index Scan using "agg_awc_2019-10-01_5_awc_id_idx" on "agg_awc_2019-10-01_5" agg_awc_3  (cost=0.55..0.77 rows=1 width=189)
                           Index Cond: (awc_location_1.doc_id = awc_id)
                           Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 5) AND (awc_location_1.aggregation_level = aggregation_level) AND (awc_location_1.state_id = state_id) AND (awc_location_1.district_id = district_id) AND (awc_location_1.block_id = block_id) AND (awc_location_1.supervisor_id = supervisor_id))
   ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
         Filter: (start_date = '2019-11-01'::date)

*/
