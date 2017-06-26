INSERT INTO {{ user_group_dim }} (
    domain,
    user_dim_id,
    group_dim_id,
    dim_last_modified,
    dim_created_on,
    deleted
)
SELECT
    ud.domain,
    ud.id,
    gd.id,
    now(),
    now(),
    false
FROM
    {{ user_dim }} AS ud
INNER JOIN (
    SELECT
        UNNEST(user_ids) AS user_id,
        group_id
    FROM
        {{ group_staging }}
) group_user_table
ON (ud.user_id = group_user_table.user_id)
INNER JOIN
    {{ group_dim }} AS gd
ON gd.group_id = group_user_table.group_id
