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
    CASE doc_type
        WHEN 'Application' then false
        WHEN 'LinkedApplication' then false
        WHEN 'RemoteApp' then false
        WHEN 'Application-Deleted' then true
        WHEN 'LinkedApplication-Deleted' then true
        WHEN 'RemoteApp-Deleted' then true
    END,
    now(),
    now(),
    '{{ batch_id }}'
FROM {{ application_staging }}
ON CONFLICT (application_id) DO UPDATE
SET application_id = EXCLUDED.application_id
    domain = EXCLUDED.domain,
    name = EXCLUDED.name,
    application_last_modified = EXCLUDED.application_last_modified,
    deleted = EXCLUDED.deleted,
    dim_last_modified = EXCLUDED.dim_last_modified,
    dim_created_on = EXCLUDED.dim_created_on,
    batch_id = EXCLUDED.batch_id;
