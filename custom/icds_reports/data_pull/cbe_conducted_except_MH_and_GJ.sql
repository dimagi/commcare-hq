SELECT state_name, district_name,
sum(cbe_table.apr_cbe_conducted) AS "April CBE conducted",
sum(cbe_table.may_cbe_conducted) AS "May CBE conducted",
sum(cbe_table.june_cbe_conducted) AS "June CBE conducted",
sum(cbe_table.july_cbe_conducted) AS "July CBE conducted",
sum(cbe_table.aug_cbe_conducted) AS "Aug CBE conducted",
sum(cbe_table.sept_cbe_conducted) AS "Sept CBE conducted",
sum(cbe_table.oct_cbe_conducted) AS "Oct CBE conducted",
sum(cbe_table.nov_cbe_conducted) AS "Nov CBE conducted"
FROM awc_location_local awc_location
RIGHT JOIN (
  SELECT awc_id,
  LEAST(count(*) FILTER (WHERE date_cbe_organise >= '2019-04-01' AND date_cbe_organise<'2019-05-01') ,2) AS apr_cbe_conducted,
  LEAST(count(*) FILTER (WHERE date_cbe_organise >= '2019-05-01' AND date_cbe_organise<'2019-06-01') ,2) AS may_cbe_conducted,
  LEAST(count(*) FILTER (WHERE date_cbe_organise >= '2019-06-01' AND date_cbe_organise<'2019-07-01') ,2) AS june_cbe_conducted,
  LEAST(count(*) FILTER (WHERE date_cbe_organise >= '2019-07-01' AND date_cbe_organise<'2019-08-01') ,2) AS july_cbe_conducted,
  LEAST(count(*) FILTER (WHERE date_cbe_organise >= '2019-08-01' AND date_cbe_organise<'2019-09-01') ,2) AS aug_cbe_conducted,
  LEAST(count(*) FILTER (WHERE date_cbe_organise >= '2019-09-01' AND date_cbe_organise<'2019-10-01') ,2) AS sept_cbe_conducted,
  LEAST(count(*) FILTER (WHERE date_cbe_organise >= '2019-10-01' AND date_cbe_organise<'2019-11-01') ,2) AS oct_cbe_conducted,
  LEAST(count(*) FILTER (WHERE date_cbe_organise >= '2019-11-01' AND date_cbe_organise<'2019-12-01') ,2) AS nov_cbe_conducted
  FROM "ucr_icds-cas_static-cbe_form_f7988a04"
  WHERE date_cbe_organise>='2019-04-01' AND date_cbe_organise<'2019-12-01'
  AND state_id NOT IN ('d982a6fb4cca0824fbde59db18d3800f', '3518687a1a6e4b299dedfef967f29c0c')
  GROUP BY awc_id
) cbe_table ON  awc_location.doc_id = cbe_table.awc_id
WHERE awc_location.aggregation_level = 5 GROUP BY state_name, district_name
