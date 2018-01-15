INSERT INTO {{ group_dim }} (
    group_id,
    name,
    domain,
    case_sharing,
    reporting,
    group_last_modified,
    deleted,
    dim_last_modified,
    dim_created_on,
    batch_id
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
    now(),
    '{{ batch_id }}'
FROM
    {{ group_staging }}
ON CONFLICT (group_id) DO UPDATE
SET name = EXCLUDED.name,
    domain = EXCLUDED.domain,
    case_sharing = EXCLUDED.case_sharing,
    reporting = EXCLUDED.reporting,
    group_last_modified = EXCLUDED.group_last_modified,
    deleted = EXCLUDED.deleted,
    dim_last_modified = EXCLUDED.dim_last_modified,
    batch_id = EXCLUDED.batch_id;
