DROP TABLE IF EXISTS temp_bihar_api_table;
CREATE TABLE temp_bihar_api_table
  AS (
  SELECT
    bihar.person_id as person_id,
    bihar.month as month,
    bihar.supervisor_id as supervisor_id,
    person_case.age_marriage as age_marriage,
    person_case.last_referral_date as last_referral_date,
    person_case.referral_health_problem as referral_health_problem,
    person_case.referral_reached_date as referral_reached_date,
    person_case.referral_reached_facility as referral_reached_facility,
    person_case.was_oos_ever as was_oos_ever,
    person_case.last_reported_fever_date as last_reported_fever_date,
    agg_mig.migration_date as migrate_date
    FROM "bihar_api_demographics" bihar
    LEFT OUtER JOIN "ucr_icds-cas_static-person_cases_v3_2ae0879a" person_case ON bihar.person_id = person_case.doc_id AND person_case.supervisor_id = bihar.supervisor_id
    LEFT OUTER JOIN "icds_dashboard_migration_forms" agg_mig ON bihar.person_id = agg_mig.person_case_id AND bihar.supervisor_id = agg_mig.supervisor_id AND agg_mig.month='{month}'
    WHERE bihar.month='{month}'::date AND bihar.state_id='{state_id}'
  );
SELECT create_distributed_table('temp_bihar_api_table', 'supervisor_id');
UPDATE "bihar_api_demographics" bihar
SET
    age_marriage = ut.age_marriage,
    last_referral_date = ut.last_referral_date,
    referral_health_problem = ut.referral_health_problem,
    referral_reached_date = ut.referral_reached_date,
    referral_reached_facility = ut.referral_reached_facility,
    was_oos_ever = ut.was_oos_ever,
    last_reported_fever_date = ut.last_reported_fever_date,
    migrate_date = ut.migrate_date
FROM temp_bihar_api_table ut
WHERE (
    bihar.person_id = ut.person_id AND
    bihar.month = ut.month AND
    bihar.supervisor_id = ut.supervisor_id AND
    bihar.month = '{month}'
);
DROP TABLE IF EXISTS temp_bihar_api_table
