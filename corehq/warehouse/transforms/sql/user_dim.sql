INSERT INTO {{ user_dim }} (
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
    dim_created_on,
    batch_id
)
SELECT
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
    now(),
    '{{ batch_id }}'
FROM {{ user_staging }}
ON CONFLICT (user_id) DO UPDATE
SET username = EXCLUDED.username,
    user_type = EXCLUDED.user_type,
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    email = EXCLUDED.email,
    doc_type = EXCLUDED.doc_type,
    is_active = EXCLUDED.is_active,
    is_staff = EXCLUDED.is_staff,
    is_superuser = EXCLUDED.is_superuser,
    last_login = EXCLUDED.last_login,
    date_joined = EXCLUDED.date_joined,
    deleted = EXCLUDED.deleted,
    dim_last_modified = EXCLUDED.dim_last_modified,
    batch_id = EXCLUDED.batch_id;
