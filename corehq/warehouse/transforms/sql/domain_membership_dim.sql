-- remove memberships if there is update to user's domains
DELETE
FROM warehouse_domainmembershipdim AS dm_dim
WHERE dm_dim.user_dim_id IN(
    SELECT user_dim.id
    FROM warehouse_userdim as user_dim
    INNER JOIN warehouse_userstagingtable as user_staging ON
    user_staging.user_id = user_dim.user_id
);

INSERT INTO warehouse_domainmembershipdim (
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
    4
FROM
    (
    SELECT 
        user_dim.deleted,
        user_dim.id,
        json_array_elements(user_staging.domain_memberships::JSON) as memberships
    FROM warehouse_userstagingtable AS user_staging
    INNER JOIN warehouse_userdim AS user_dim 
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
    4
FROM warehouse_userstagingtable AS user_staging
INNER JOIN warehouse_userdim AS user_dim 
ON user_staging.user_id = user_dim.user_id
WHERE user_staging.doc_type = 'CommCareUser';
