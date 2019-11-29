-- get all not test state_ids
SELECT distinct(state_id), state_name FROM awc_location where state_is_test=0;

/*
             state_id             |        state_name
----------------------------------+---------------------------
 f9b47ea2ee2d8a02acddeeb491d3e175 | Bihar
 e6d00bd20f43438c87c9d93ec22022ef | J&K
 a2fcb186e9be8464e167bb1c56ce8fd9 | Chhattisgarh
 3eac9afdbca1423786e3166ff81b5178 | Uttarakhand
 e8984699e07c44eda4f86860a6262703 | Nagaland
 1202da3463224bd2b48ac5cb8ccebbc1 | Himachal Pradesh
 5e01a377aa7b4cdcb73ac6f009368ddc | Puducherry
 dab47c2c5c75484e979a24a63e8490bd | Chandigarh
 96dacff698ed4ea2be48a5c952646114 | Tamil Nadu
 d982a6fb4cca0824fbde59db18d3800f | Madhya Pradesh
 6beb6eaeea7941dd9ff6f2110f1acdb0 | Telangana
 d11eb832e00747b9831de08c29d676ad | Goa
 989bb41a8c204f71990bddc4783d0d33 | Meghalaya
 f98e91aa003accb7b849a0f18ebd7039 | Andhra Pradesh
 039bbe4a40de499ea87b9761537dd611 | Andaman & Nicobar Islands
 085a5fd73e9741e69b19aaac155ba132 | Manipur
 2af81d10b2ca4229a54bab97a5150538 | Maharashtra
 9051ef4f91d54a89b89c533780857e05 | Uttar Pradesh
 e2963f2eec18488d8016c22fb0c38a3c | Sikkim
 35408087a908448a849dc48e336a9fc3 | Lakshadweep
 c7985cd779924b62b9eb863cea8e63b7 | Daman & Diu
 9cd4fd88d9f047088a377b7e7d144830 | Rajasthan
 4c84a44ded2b4b00b27373070332849f | Assam
 77906526407b41049f1309be323614d3 | Dadra & Nagar Haveli
 f1cd643f0df908421abd915298ba57bc | Jharkhand
 3518687a1a6e4b299dedfef967f29c0c | Gujarat
 32c6b88173cc49ea82e804292e97c3f0 | Kerala
 e1f3a4c8b1264042893816f1ae48819c | Delhi
 e4cb09f85b5947689ebc35d0789e0bda | Mizoram
*/


COPY(SELECT mobile_number AS "Mobile Number", state_name
FROM ccs_record_monthly
RIGHT JOIN awc_location loc
ON (loc.doc_id=ccs_record_monthly.awc_id AND loc.supervisor_id=ccs_record_monthly.supervisor_id)
WHERE
closed=0 AND -- or use open_in_month=1 this IS already covered by valid_in_month but if this does NOT add extra cost, keep it FOR safety
valid_in_month=1 AND
length(mobile_number) > 0 AND
month='2019-11-01'
) TO '/tmp/phone_numbers_mothers.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

/*
  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
   Task Count: 64
   Tasks Shown: One of 64
   ->  Task
         Node: host=100.71.184.232 port=6432 dbname=icds_ucr
         ->  Gather  (cost=1000.55..110512.17 rows=1 width=15)
               Workers Planned: 5
               ->  Nested Loop  (cost=0.55..109512.07 rows=1 width=15)
                     ->  Parallel Seq Scan on ccs_record_monthly_102712 ccs_record_monthly  (cost=0.00..105778.36 rows=1479 width=71)
                           Filter: ((closed = 0) AND (valid_in_month = 1) AND (month = '2019-11-01'::date) AND (length(mobile_number) > 0))
                     ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 loc  (cost=0.55..2.51 rows=1 width=73)
                           Index Cond: (doc_id = ccs_record_monthly.awc_id)
                           Filter: (ccs_record_monthly.supervisor_id = supervisor_id)
(13 rows)
*/

COPY(SELECT mother_phone_number AS "Mobile Number", state_name
FROM child_health_monthly
RIGHT JOIN awc_location loc
ON (loc.doc_id=child_health_monthly.awc_id AND loc.supervisor_id=child_health_monthly.supervisor_id)
WHERE
open_in_month=1 AND -- or use closed=0 this IS already covered by valid_in_month but if this does NOT add extra cost, keep it FOR safety
valid_in_month=1 AND
length(mother_phone_number) > 0 AND
month='2019-11-01'
) TO '/tmp/phone_numbers_children.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

/*
  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
   Task Count: 64
   Tasks Shown: One of 64
   ->  Task
         Node: host=100.71.184.232 port=6432 dbname=icds_ucr
         ->  Gather  (cost=16985.84..531931.93 rows=10 width=13)
               Workers Planned: 6
               ->  Nested Loop  (cost=15985.84..530930.93 rows=2 width=13)
                     ->  Parallel Bitmap Heap Scan on child_health_monthly_102648 child_health_monthly  (cost=15985.29..496444.10 rows=33390 width=69)
                           Recheck Cond: (month = '2019-11-01'::date)
                           Filter: ((open_in_month = 1) AND (valid_in_month = 1) AND (length(mother_phone_number) > 0))
                           ->  Bitmap Index Scan on chm_month_supervisor_id_102648  (cost=0.00..15935.21 rows=712660 width=0)
                                 Index Cond: (month = '2019-11-01'::date)
                     ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 loc  (cost=0.55..1.02 rows=1 width=73)
                           Index Cond: (doc_id = child_health_monthly.awc_id)
                           Filter: (child_health_monthly.supervisor_id = supervisor_id)
(16 rows)
(16 rows)(16 rows)
*/
