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
    combined_user_group_table.deleted
FROM
(
(
    SELECT
        UNNEST(user_ids) AS user_id,
        group_id AS group_id,
        false AS deleted
    FROM
        {{ group_staging }}
)

UNION

(
    SELECT
        UNNEST(removed_user_ids) AS removed_user_id,
        group_id AS group_id,
        true AS deleted
    FROM
        {{ group_staging }}
)
) combined_user_group_table
INNER JOIN {{ group_dim }} AS gd
ON combined_user_group_table.group_id = gd.group_id

INNER JOIN {{ user_dim }} AS ud
ON combined_user_group_table.user_id = ud.user_id
