SELECT
    awc.state_name,
    awc.district_name,
    awc.block_name,
    awc.supervisor_name,
    awc.awc_name,
    ccs.person_name,
    CASE WHEN ccs.pregnant=1 THEN 'PW' ELSE 'LW' END,
    age(NOW(), ccs.dob) as age
    FROM "ccs_record_monthly" ccs
    LEFT JOIN "awc_location" awc ON (
        awc.doc_id = ccs.awc_id
        AND awc.supervisor_id = ccs.supervisor_id
    )
    WHERE
    ccs.age_in_months >= 132 AND ccs.age_in_months<168
    AND (ccs.pregnant=1 OR ccs.lactating=1);
