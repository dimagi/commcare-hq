SELECT
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
    date_joined
FROM {{ user_staging }}
