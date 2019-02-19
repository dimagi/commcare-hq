-- remove memberships if there is update to user's domains
DELETE
FROM {{ domain_membership_dim }} AS dm_dim
WHERE dm_dim.user_dim_id IN(
    SELECT user_dim.id
    FROM {{ user_dim }} as user_dim
    INNER JOIN {{ user_staging }} as user_staging ON
    user_staging.user_id = user_dim.user_id
);

INSERT INTO {{ domain_membership_dim }} (
    dim_last_modified,
    dim_created_on,
    user_dim_id,
    domain,
    is_domain_admin,
    deleted,
    batch_id
)
-- webuser memberships
SELECT
    now(),
    now(),
    ddm.id as user_dim_id,
    (ddm.memberships ->> 'domain') as domain,
    (ddm.memberships ->> 'is_admin')::boolean as is_domain_admin,
    ddm.deleted,
    {{ batch_id }}
FROM
    (
    SELECT 
        user_dim.deleted,
        user_dim.id,
        json_array_elements(user_staging.domain_memberships::JSON) as memberships
    FROM {{ user_staging }} AS user_staging
    LEFT JOIN {{ user_dim }} AS user_dim
    ON user_staging.user_id = user_dim.user_id
    WHERE user_staging.doc_type = 'WebUser'
) ddm    
UNION    
-- mobile user memberships
SELECT
    now(),
    now(),
    user_dim.id as user_dim_id,
    user_staging.domain,
    false as is_domain_admin,
    user_dim.deleted,
    {{ batch_id }}
FROM {{ user_staging }} AS user_staging
LEFT JOIN {{ user_dim }} AS user_dim
ON user_staging.user_id = user_dim.user_id
WHERE user_staging.doc_type = 'CommCareUser';
