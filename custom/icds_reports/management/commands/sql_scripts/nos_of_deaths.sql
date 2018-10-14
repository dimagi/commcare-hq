
SELECT
  convert_to(state, 'UTF8') AS state,
  convert_to(district, 'UTF8') AS district,
  convert_to(awc, 'UTF8') AS AWC,
  death_month,
  count(*) as no_of_deaths
FROM (
      SELECT awc_location.state_name AS state,
             awc_location.district_name AS district,
             awc_location.awc_name AS awc,
             date_trunc('month',person_case.date_death) as death_month
      FROM "%(person_table_name)s" AS person_case
      INNER JOIN "%(awc_location_table_name)s" AS awc_location
      ON person_case.awc_id = awc_location.doc_id
      WHERE date_death IS NOT NULL) AS joined_result
GROUP BY state,district,awc, death_month;