INSERT INTO {{ domain_dim }} (
    domain_id,
    domain,
    default_timezone,
    hr_name,
    creating_user_id,
    project_type,
    deleted,
    is_active,
    case_sharing,
    commtrack_enabled,
    is_test,
    location_restriction_for_users,
    use_sql_backend,
    first_domain_for_user,
    domain_last_modified,
    domain_created_on,
    dim_last_modified,
    dim_created_on
)
SELECT
    domain_id,
    domain,
    default_timezone,
    hr_name,
    creating_user_id,
    project_type,
    CASE
        WHEN doc_type = 'Domain' THEN false
        WHEN doc_type LIKE 'Domain-Deleted%' THEN true
    END,
    is_active,
    case_sharing,
    commtrack_enabled,
    CASE is_test
        WHEN 'none' THEN false
        WHEN 'true' THEN true
        WHEN 'false' THEN false
    END,
    location_restriction_for_users,
    -- Ensures all the boolean values are either true or false
    use_sql_backend,
    first_domain_for_user,
    domain_last_modified,
    domain_created_on,
    now(),
    now()
FROM
    {{ domain_staging }}
