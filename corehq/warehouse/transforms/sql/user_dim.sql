INSERT INTO {{ user_dim }} (
    domain,
    user_id,
    username,
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
    first_name,
    last_name,
    email,
    doc_type,
    CASE is_active
        WHEN is_active OR is_active IS NULL THEN true
        ELSE false
    END,
    CASE is_staff
        WHEN is_staff THEN true
        ELSE false
    END,
    CASE is_superuser
        WHEN is_superuser THEN true
        ELSE false
    END,
    last_login,
    date_joined,
    CASE base_doc
        WHEN 'CouchUser' THEN false
        WHEN 'CouchUser-Deleted' THEN true
    END,
    now(),
    now()
FROM {{ user_staging }}
