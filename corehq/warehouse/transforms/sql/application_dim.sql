INSERT INTO {{ application_dim }} (
    application_id,
    domain,
    name,
    application_last_modified,
    deleted,
    dim_last_modified,
    dim_created_on,
    batch_id
)
SELECT
    application_id,
    domain,
    name,
    application_last_modified,
    CASE base_doc
        WHEN 'ApplicationBase' then false
        WHEN 'ApplicationBase-Deleted' then true
    END,
    now(),
    now(),
    '{{ batch_id }}'
FROM {{ application_staging }}
