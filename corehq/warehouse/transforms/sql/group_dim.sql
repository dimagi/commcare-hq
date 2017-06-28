INSERT INTO {{ group_dim }} (
    group_id,
    name,
    domain,
    case_sharing,
    reporting,
    group_last_modified,
    deleted,
    dim_last_modified,
    dim_created_on
)
SELECT
    group_id,
    name,
    domain,
    case_sharing,
    reporting,
    group_last_modified,
    CASE
        WHEN doc_type = 'Group' THEN false
        WHEN doc_type LIKE 'Group-Deleted%' THEN true
    END,
    now(),
    now()
FROM
    {{ group_staging }}
