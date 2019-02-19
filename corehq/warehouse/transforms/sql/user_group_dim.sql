-- First delete all records in UserGroupDim that are in the
-- GroupStagingTable
DELETE FROM {{ user_group_dim }} AS ug_dim
USING {{ group_staging }} AS group_staging
INNER JOIN {{ group_dim }} AS gd
ON gd.group_id = group_staging.group_id

WHERE ug_dim.group_dim_id = gd.id;

-- Repopulate the UserGroupDim
INSERT INTO {{ user_group_dim }} (
    domain,
    user_dim_id,
    group_dim_id,
    dim_last_modified,
    dim_created_on,
    deleted,
    batch_id
)

SELECT
    gd.domain,
    ud.id,
    gd.id,
    now(),
    now(),
    false,
    '{{ batch_id }}'
FROM
(
    SELECT
        UNNEST(user_ids) AS user_id,
        group_id AS group_id
    FROM
        {{ group_staging }}
    WHERE doc_type = 'Group'
) user_group_table
LEFT JOIN {{ group_dim }} AS gd
ON user_group_table.group_id = gd.group_id

LEFT JOIN {{ user_dim }} AS ud
ON user_group_table.user_id = ud.user_id;
