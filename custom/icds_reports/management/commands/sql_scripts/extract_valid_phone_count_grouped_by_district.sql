SELECT 
person_cases.district_id,
person_cases.state_id,
-- Pregnant Women
SUM(
    CASE 
        WHEN is_pregnant = 1 
            THEN 1 
        ELSE 0
    END) "pw_count",
SUM(
    CASE 
        WHEN is_pregnant = 1 
        AND phone_number similar to '91[6789][0-9]{9}' THEN 1 else 0
    END) "pw_valid_phone_count",
SUM(
    CASE
        WHEN is_pregnant = 1
        AND (phone_number = '') IS NOT FALSE  THEN 1 ELSE 0
    END) "pw_phone_not_available",
SUM(
    CASE WHEN is_pregnant = 1 
    AND (phone_number = '') IS FALSE AND phone_number NOT SIMILAR to '91[6789][0-9]{9}' THEN 1 ELSE 0
    END) "pw_invalid_phone_count",

-- Lactating Mother
SUM(
    CASE 
        WHEN ccs_record.add is not null AND ccs_record.add - now() < '182 days' :: interval 
            THEN 1 
        ELSE 0
    END) "lm_count",
SUM(
    CASE 
        WHEN ccs_record.add is not null AND ccs_record.add - now() < '182 days':: interval 
        AND phone_number similar to '91[6789][0-9]{9}' THEN 1 else 0
    END) "lm_valid_phone_count",
SUM(
    CASE
        WHEN ccs_record.add is not null AND ccs_record.add - now() < '182 days' :: interval
        AND (phone_number = '') IS NOT FALSE  THEN 1 ELSE 0
    END) "lm_phone_not_available",
SUM(
    CASE WHEN ccs_record.add is not null AND ccs_record.add - now() < '182 days' :: interval 
    AND (phone_number = '') IS FALSE AND phone_number NOT SIMILAR to '91[6789][0-9]{9}' THEN 1 ELSE 0
    END) "lm_invalid_phone_count",


-- Children
SUM(
    CASE 
        WHEN child_health.dob is NOT null AND now() - child_health.dob <= '2191.5 days' ::interval  
            THEN 1 
        ELSE 0
    END) "children_count",
SUM(
    CASE 
        WHEN child_health.dob is NOT null AND now() - child_health.dob <= '2191.5 days' ::interval  
        AND phone_number similar to '91[6789][0-9]{9}' THEN 1 else 0
    END) "children_valid_phone_count",
SUM(
    CASE
        WHEN child_health.dob is NOT null AND now() - child_health.dob <= '2191.5 days' ::interval
        AND (phone_number = '') IS NOT FALSE  THEN 1 ELSE 0
    END) "children_phone_not_available",
SUM(
    CASE WHEN child_health.dob is NOT null AND now() - child_health.dob <= '2191.5 days' ::interval
    AND (phone_number = '') IS FALSE AND phone_number NOT SIMILAR to '91[6789][0-9]{9}' THEN 1 ELSE 0
    END) "children_invalid_phone_count",

-- Women 
SUM(
    CASE 
        WHEN person_cases.sex = 'f' AND now() - person_cases.dob >= '4017.75 days' ::interval 
            THEN 1 
        ELSE 0
    END) "women_count",
SUM(
    CASE 
        WHEN person_cases.sex = 'f' AND now() - person_cases.dob >= '4017.75 days' ::interval 
        AND phone_number similar to '91[6789][0-9]{9}' THEN 1 else 0
    END) "women_valid_phone_count",
SUM(
    CASE
        WHEN person_cases.sex = 'f' AND now() - person_cases.dob >= '4017.75 days' ::interval
        AND (phone_number = '') IS NOT FALSE  THEN 1 ELSE 0
    END) "women_phone_not_available",
SUM(
    CASE WHEN person_cases.sex = 'f' AND now() - person_cases.dob >= '4017.75 days' ::interval 
    AND (phone_number = '') IS FALSE AND phone_number NOT SIMILAR to '91[6789][0-9]{9}' THEN 1 ELSE 0
    END) "women_invalid_phone_count"

FROM "ucr_icds-cas_static-person_cases_v3_2ae0879a" person_cases

LEFT OUTER JOIN "ucr_icds-cas_static-child_health_cases_a46c129f" child_health

ON 
    child_health.mother_id = person_cases.doc_id 
    AND 
    child_health.state_id = person_cases.state_id 
    AND 
    child_health.supervisor_id = person_cases.supervisor_id
LEFT OUTER JOIN "ucr_icds-cas_static-ccs_record_cases_cedcca39" ccs_record 
ON  
    ccs_record.person_case_id = person_cases.doc_id
    AND 
    ccs_record.supervisor_id = person_cases.supervisor_id
GROUP BY person_cases.state_id, person_cases.district_id