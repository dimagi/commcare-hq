INSERT INTO {{ user_dim }} (
    domain,
    user_id,
    username,
    user_type,
    first_name,
    last_name,
    email,
    doc_type,
    is_active,
    is_staff,
    is_superuser,
    last_login,
    date_joined,
    deleted,
    dim_last_modified,
    dim_created_on
)
SELECT
    domain,
    user_id,
    username,
    CASE
        WHEN user_id = 'system' THEN 'system'
        WHEN user_id = 'demo_user' THEN 'demo'
        WHEN user_id = 'commtrack-system' THEN 'supply'
        WHEN doc_type = 'WebUser' THEN 'web'
        WHEN doc_type = 'CommCareUser' THEN 'mobile'
        ELSE 'unknown'
    END,
    first_name,
    last_name,
    email,
    doc_type,
    is_active,
    is_staff,
    is_superuser,
    last_login,
    date_joined,
    CASE base_doc
        WHEN 'CouchUser' THEN false
        WHEN 'CouchUser-Deleted' THEN true
    END,
    now(),
    now()
FROM {{ user_staging }}
