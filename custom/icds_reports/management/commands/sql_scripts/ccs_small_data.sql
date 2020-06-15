SELECT
    count(*) filter (where age_in_months<216) as mother_lt_18,
    count(*) filter (where age_in_months=>216 and age_in_months<=240) as mother_18_20,
    count(*) filter (where age_in_months>=216 ) as mother_gt_18,
    count(*) filter (where age_in_months=>132 and age_in_months<168) as mother_11_14,
    count(*) filter (where age_in_months>=240 ) as mother_gt_20
FROM ccs_record_monthly
WHERE pregnant=1 or lactating=1;
