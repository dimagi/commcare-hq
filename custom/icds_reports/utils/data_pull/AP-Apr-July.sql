WRAPPER
COPY (
) To STDOUT DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


LUNCH 1
[done][Ran by Rohit Negi]
COPY (
select district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,
SUM(pse_eligible) as lunch_eligible,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END) as lunch_0,
CASE WHEN SUM(pse_eligible) is not null  and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_0,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END) as lunch_1_7,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_1_7,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)as  lunch_8_14,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_8_14,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)as lunch_15_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_15_21,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END) as lunch_gt_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 AND awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-04-01'
    )
WHERE child_health.age_in_months>36 and aggregation_level=5
group by  district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/lunch_Apr_3_6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


[done]
COPY (
select district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,
SUM(pse_eligible) as lunch_eligible,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END) as lunch_0,
CASE WHEN SUM(pse_eligible) is not null  and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_0,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END) as lunch_1_7,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_1_7,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)as  lunch_8_14,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_8_14,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)as lunch_15_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_15_21,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END) as lunch_gt_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 AND awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-05-01'
    )
WHERE child_health.age_in_months>36 and aggregation_level=5
group by  district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/lunch_May_3_6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

[done]
COPY (
select district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,
SUM(pse_eligible) as lunch_eligible,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END) as lunch_0,
CASE WHEN SUM(pse_eligible) is not null  and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_0,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END) as lunch_1_7,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_1_7,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)as  lunch_8_14,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_8_14,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)as lunch_15_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_15_21,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END) as lunch_gt_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 AND awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-06-01'
    )
WHERE child_health.age_in_months>36 and aggregation_level=5
group by  district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/lunch_June_3_6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

[done]
COPY (
select district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,
SUM(pse_eligible) as lunch_eligible,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END) as lunch_0,
CASE WHEN SUM(pse_eligible) is not null  and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_0,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END) as lunch_1_7,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_1_7,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)as  lunch_8_14,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_8_14,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)as lunch_15_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_15_21,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END) as lunch_gt_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 AND awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-07-01'
    )
WHERE child_health.age_in_months>36 and aggregation_level=5
group by  district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/lunch_July_3_6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


LUNCH 2
[done]
COPY (
select district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,
SUM(pse_eligible) as lunch_eligible,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END) as lunch_0,
CASE WHEN SUM(pse_eligible) is not null  and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_0,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END) as lunch_1_7,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_1_7,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)as  lunch_8_14,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_8_14,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)as lunch_15_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_15_21,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END) as lunch_gt_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 AND awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-04-01'
    )
WHERE child_health.age_in_months>60 and awc_location.aggregation_level=5
group by  district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/lunch_Apr_5_6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


[done]
COPY (
select district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,
SUM(pse_eligible) as lunch_eligible,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END) as lunch_0,
CASE WHEN SUM(pse_eligible) is not null  and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_0,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END) as lunch_1_7,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_1_7,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)as  lunch_8_14,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_8_14,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)as lunch_15_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_15_21,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END) as lunch_gt_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 AND awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-05-01'
    )
WHERE child_health.age_in_months>60 and awc_location.aggregation_level=5
group by  district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/lunch_May_5_6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

[done]
COPY (
select district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,
SUM(pse_eligible) as lunch_eligible,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END) as lunch_0,
CASE WHEN SUM(pse_eligible) is not null  and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_0,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END) as lunch_1_7,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_1_7,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)as  lunch_8_14,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_8_14,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)as lunch_15_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_15_21,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END) as lunch_gt_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 AND awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-06-01'
    )
WHERE child_health.age_in_months>60 and awc_location.aggregation_level=5
group by  district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/lunch_June_5_6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

[done]
COPY (
select district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,
SUM(pse_eligible) as lunch_eligible,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END) as lunch_0,
CASE WHEN SUM(pse_eligible) is not null  and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count=0 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_0,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END) as lunch_1_7,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_1_7,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)as  lunch_8_14,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count BETWEEN 8 and 14 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_8_14,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)as lunch_15_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count between 15 and 21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_15_21,
SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END) as lunch_gt_21,
CASE WHEN SUM(pse_eligible) is not null and SUM(pse_eligible)>0 THEN SUM(CASE WHEN lunch_count is not null and pse_eligible=1 and lunch_count>21 then 1 ELSE 0 END)::float/SUM(pse_eligible)*100 ELSE 0 END as percent_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 AND awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-07-01'
    )
WHERE child_health.age_in_months>60 and awc_location.aggregation_level=5
group by  district_name, block_name,supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/lunch_July_5_6.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


THR 1
[done]
COPY (
select district_name,block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(CASE WHEN thr_eligible is not null then thr_eligible ELSE 0 END) as mother_thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END) as mother_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_0,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END) as mother_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_1_7,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END) as mother_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_8_14,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END) as mother_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_15_21,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed>21 THEN 1 else 0 END) as mother_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN  SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1  and num_rations_distributed>21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_gt_21,
month
from  awc_location inner join
"ccs_record_monthly" ccs_record on (awc_location.doc_id=ccs_record.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0  AND
    awc_location.supervisor_id = ccs_record.supervisor_id AND
    pregnant=1 and lactating=0 and ccs_record.month = '2019-04-01'
    )
WHERE awc_location.aggregation_level=5
group by  district_name, block_name, supervisor_name,awc_location.supervisor_id,awc_name, month
) To '/tmp/thr_preg_Apr.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


[done]
COPY (
select district_name,block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(CASE WHEN thr_eligible is not null then thr_eligible ELSE 0 END) as mother_thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END) as mother_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_0,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END) as mother_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_1_7,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END) as mother_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_8_14,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END) as mother_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_15_21,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed>21 THEN 1 else 0 END) as mother_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN  SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1  and num_rations_distributed>21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_gt_21,
month
from  awc_location inner join
"ccs_record_monthly" ccs_record on (awc_location.doc_id=ccs_record.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0  AND
    awc_location.supervisor_id = ccs_record.supervisor_id AND
    pregnant=1 and lactating=0 and ccs_record.month = '2019-05-01'
    )
WHERE awc_location.aggregation_level=5
group by  district_name, block_name, supervisor_name,awc_location.supervisor_id,awc_name, month
) To '/tmp/thr_preg_May.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


[done]
COPY (
select district_name,block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(CASE WHEN thr_eligible is not null then thr_eligible ELSE 0 END) as mother_thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END) as mother_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_0,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END) as mother_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_1_7,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END) as mother_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_8_14,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END) as mother_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_15_21,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed>21 THEN 1 else 0 END) as mother_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN  SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1  and num_rations_distributed>21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_gt_21,
month
from  awc_location inner join
"ccs_record_monthly" ccs_record on (awc_location.doc_id=ccs_record.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0  AND
    awc_location.supervisor_id = ccs_record.supervisor_id AND
    pregnant=1 and lactating=0 and ccs_record.month = '2019-06-01'
    )
WHERE awc_location.aggregation_level=5
group by  district_name, block_name, supervisor_name,awc_location.supervisor_id,awc_name, month
) To '/tmp/thr_preg_June.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

[done]
COPY (
select district_name,block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(CASE WHEN thr_eligible is not null then thr_eligible ELSE 0 END) as mother_thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END) as mother_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_0,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END) as mother_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_1_7,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END) as mother_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_8_14,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END) as mother_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_15_21,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed>21 THEN 1 else 0 END) as mother_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN  SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1  and num_rations_distributed>21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_gt_21,
month
from  awc_location inner join
"ccs_record_monthly" ccs_record on (awc_location.doc_id=ccs_record.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0  AND
    awc_location.supervisor_id = ccs_record.supervisor_id AND
    pregnant=1 and lactating=0 and ccs_record.month = '2019-07-01'
    )
WHERE awc_location.aggregation_level=5
group by  district_name, block_name, supervisor_name,awc_location.supervisor_id,awc_name, month
) To '/tmp/thr_preg_July.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


THR 2
[done]
COPY (
select district_name,block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(CASE WHEN thr_eligible is not null then thr_eligible ELSE 0 END) as mother_thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END) as mother_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_0,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END) as mother_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_1_7,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END) as mother_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_8_14,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END) as mother_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_15_21,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed>21 THEN 1 else 0 END) as mother_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN  SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1  and num_rations_distributed>21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_gt_21,
month
from  awc_location inner join
"ccs_record_monthly" ccs_record on (awc_location.doc_id=ccs_record.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 and awc_location.supervisor_id = ccs_record.supervisor_id AND
    pregnant=0 and lactating=1 and ccs_record.month = '2019-04-01'
    )
WHERE awc_location.aggregation_level=5
group by  district_name, block_name,  supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/thr_lact_Apr.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


[done]
COPY (
select district_name,block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(CASE WHEN thr_eligible is not null then thr_eligible ELSE 0 END) as mother_thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END) as mother_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_0,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END) as mother_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_1_7,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END) as mother_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_8_14,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END) as mother_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_15_21,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed>21 THEN 1 else 0 END) as mother_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN  SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1  and num_rations_distributed>21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_gt_21,
month
from  awc_location inner join
"ccs_record_monthly" ccs_record on (awc_location.doc_id=ccs_record.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 and awc_location.supervisor_id = ccs_record.supervisor_id AND
    pregnant=0 and lactating=1 and ccs_record.month = '2019-05-01'
    )
WHERE awc_location.aggregation_level=5
group by  district_name, block_name,  supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/thr_lact_May.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

[done]
COPY (
select district_name,block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(CASE WHEN thr_eligible is not null then thr_eligible ELSE 0 END) as mother_thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END) as mother_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_0,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END) as mother_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_1_7,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END) as mother_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_8_14,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END) as mother_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_15_21,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed>21 THEN 1 else 0 END) as mother_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN  SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1  and num_rations_distributed>21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_gt_21,
month
from  awc_location inner join
"ccs_record_monthly" ccs_record on (awc_location.doc_id=ccs_record.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 and awc_location.supervisor_id = ccs_record.supervisor_id AND
    pregnant=0 and lactating=1 and ccs_record.month = '2019-06-01'
    )
WHERE awc_location.aggregation_level=5
group by  district_name, block_name,  supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/thr_lact_June.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

[done]
COPY (
select district_name,block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(CASE WHEN thr_eligible is not null then thr_eligible ELSE 0 END) as mother_thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END) as mother_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed=0 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_0,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END) as mother_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN 1 and 7 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_1_7,

SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END) as mother_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  8 and 14 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_8_14,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END) as mother_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed BETWEEN  15 and 21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_15_21,


SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1 and num_rations_distributed>21 THEN 1 else 0 END) as mother_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN  SUM(CASE WHEN num_rations_distributed is not null and thr_eligible=1  and num_rations_distributed>21 THEN 1 else 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_mother_thr_gt_21,
month
from  awc_location inner join
"ccs_record_monthly" ccs_record on (awc_location.doc_id=ccs_record.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 and awc_location.supervisor_id = ccs_record.supervisor_id AND
    pregnant=0 and lactating=1 and ccs_record.month = '2019-07-01'
    )
WHERE awc_location.aggregation_level=5
group by  district_name, block_name,  supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/thr_lact_July.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


THR 3
[done]
COPY (
select district_name, block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(thr_eligible) as thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed=0 then 1 ELSE 0 END) as child_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed=0 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_0,

SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed BETWEEN 1 and 7 then 1 ELSE 0 END) as child_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_1_7,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=8 and num_rations_distributed<=14 then 1 ELSE 0 END)as  child_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=8 and num_rations_distributed<=14 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_8_14,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=15 and num_rations_distributed<=21 then 1 ELSE 0 END)as child_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=15 and num_rations_distributed<=21 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_15_21,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>21 then 1 ELSE 0 END) as child_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>21 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 and awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-04-01'
    )
WHERE thr_eligible=1 and awc_location.aggregation_level=5
group by  district_name, block_name,  supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/thr_child_Apr.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

[done]
COPY (
select district_name, block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(thr_eligible) as thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed=0 then 1 ELSE 0 END) as child_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed=0 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_0,

SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed BETWEEN 1 and 7 then 1 ELSE 0 END) as child_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_1_7,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=8 and num_rations_distributed<=14 then 1 ELSE 0 END)as  child_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=8 and num_rations_distributed<=14 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_8_14,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=15 and num_rations_distributed<=21 then 1 ELSE 0 END)as child_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=15 and num_rations_distributed<=21 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_15_21,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>21 then 1 ELSE 0 END) as child_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>21 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 and awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-05-01'
    )
WHERE thr_eligible=1 and awc_location.aggregation_level=5
group by  district_name, block_name,  supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/thr_child_May.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

[done]
COPY (
select district_name, block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(thr_eligible) as thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed=0 then 1 ELSE 0 END) as child_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed=0 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_0,

SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed BETWEEN 1 and 7 then 1 ELSE 0 END) as child_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_1_7,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=8 and num_rations_distributed<=14 then 1 ELSE 0 END)as  child_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=8 and num_rations_distributed<=14 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_8_14,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=15 and num_rations_distributed<=21 then 1 ELSE 0 END)as child_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=15 and num_rations_distributed<=21 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_15_21,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>21 then 1 ELSE 0 END) as child_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>21 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 and awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-06-01'
    )
WHERE thr_eligible=1 and awc_location.aggregation_level=5
group by  district_name, block_name,  supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/thr_child_June.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

[done]
COPY (
select district_name, block_name, supervisor_name,awc_location.supervisor_id,awc_name,
SUM(thr_eligible) as thr_eligible,

SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed=0 then 1 ELSE 0 END) as child_thr_0,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed=0 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_0,

SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed BETWEEN 1 and 7 then 1 ELSE 0 END) as child_thr_1_7,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed BETWEEN 1 and 7 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_1_7,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=8 and num_rations_distributed<=14 then 1 ELSE 0 END)as  child_thr_8_14,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=8 and num_rations_distributed<=14 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_8_14,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=15 and num_rations_distributed<=21 then 1 ELSE 0 END)as child_thr_15_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>=15 and num_rations_distributed<=21 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_15_21,
SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>21 then 1 ELSE 0 END) as child_thr_gt_21,
CASE WHEN SUM(thr_eligible) is not null and SUM(thr_eligible)>0 THEN SUM(CASE WHEN num_rations_distributed is not null and num_rations_distributed>21 then 1 ELSE 0 END)::float/SUM(thr_eligible)*100 ELSE 0 END as percent_child_thr_gt_21,
month
from  awc_location left join
"child_health_monthly" child_health on (awc_location.doc_id=child_health.awc_id and
    awc_location.state_id='f98e91aa003accb7b849a0f18ebd7039' and
    district_is_test=0 and awc_location.supervisor_id = child_health.supervisor_id AND child_health.month='2019-07-01'
    )
WHERE thr_eligible=1 and awc_location.aggregation_level=5
group by  district_name, block_name,  supervisor_name,awc_location.supervisor_id,awc_name,month
) To '/tmp/thr_child_July.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
