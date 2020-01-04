select district_name, age_tranche, has_aadhar as "Adhaar Seeded", valid as "Total"
FROM awc_location_local awc_location
LEFT JOIN (SELECT
district_id, age_tranche, sum(has_aadhar_id) AS has_aadhar, sum(valid_in_month) AS valid, aggregation_level
FROM "public"."agg_child_health" "agg_child_health" 
WHERE agg_child_health.month='2019-12-01' 
AND agg_child_health.state_id='2af81d10b2ca4229a54bab97a5150538'
AND agg_child_health.aggregation_level=2
GROUP BY age_tranche, district_id, aggregation_level) ut
ON awc_location.district_id=ut.district_id 
AND awc_location.aggregation_level=ut.aggregation_level
where awc_location.aggregation_level=2 and awc_location.state_id='2af81d10b2ca4229a54bab97a5150538'
ORDER BY district_name, age_tranche::INTEGER

