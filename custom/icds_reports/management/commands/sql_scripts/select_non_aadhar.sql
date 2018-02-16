SELECT
  convert_to(name, 'UTF8'),
  dob,
  convert_to(awc_location.awc_name, 'UTF8'),
  convert_to(awc_location.block_name, 'UTF8'),
  convert_to(awc_location.district_name, 'UTF8'),
  convert_to(awc_location.state_name, 'UTF8')
FROM "%(person_table_name)s" AS person_cases
  JOIN "%(awc_location_table_name)s" AS awc_location
    ON person_cases.awc_id = awc_location.doc_id
WHERE date_death IS NULL AND aadhar_date IS NULL AND seeking_services = 1 AND
      ((dob BETWEEN NOW() - '6 years' :: INTERVAL AND NOW()) OR
       (sex = 'F' AND dob BETWEEN NOW() - '49 years' :: INTERVAL AND NOW() - '11 years' :: INTERVAL));
