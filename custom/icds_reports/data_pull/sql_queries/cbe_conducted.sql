SELECT district_name,
       block_name,
       supervisor_name,
       awc_name,
       cbe_table.cbe_conducted
FROM awc_location_local awc_location
INNER JOIN
  (SELECT awc_id,
          count(*) AS cbe_conducted
   FROM "ucr_icds-cas_static-cbe_form_f7988a04"
   WHERE date_cbe_organise>='{from_date}'
     AND date_cbe_organise<'{till_date}'
   GROUP BY awc_id) cbe_table ON awc_location.doc_id=cbe_table.awc_id
WHERE awc_location.aggregation_level=5
  AND awc_location.state_id='{location_id}'
