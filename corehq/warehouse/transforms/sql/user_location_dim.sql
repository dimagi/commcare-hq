--- Delete all records that appear in the user staging table
DELETE FROM {{ user_location_dim }} as ul_dim
USING {{ user_staging }} as user_staging
INNER JOIN {{ user_dim }} as ud
ON ud.user_id = user_staging.user_id

WHERE ul_dim.user_dim_id = ud.id;


--- Repopulate the UserLocationDim
INSERT INTO {{ user_location_dim }} (
       domain,
       user_dim_id,
       location_dim_id,
       dim_last_modified,
       dim_created_on,
       deleted,
       batch_id
)
--- webusers
SELECT
	domain,
	user_dim_id,
	location_dim_id,
	now(),
	now(),
	false,
	{{ batch_id }}
FROM
(
	SELECT
		user_dim.id as user_dim_id,
		json_array_elements(json_array_elements(user_staging.domain_memberships::JSON) -> 'assigned_location_ids') as location_id,
		json_array_elements(user_staging.domain_memberships::JSON) ->> 'domain' as domain,
		location_dim.id as location_dim_id
	FROM {{ user_staging }} as user_staging
	LEFT JOIN {{ user_dim }} as user_dim
	ON user_staging.user_id = user_dim.user_id
	LEFT JOIN {{ location_dim }} as location_dim
	ON location_id = location_dim.location_id
	WHERE user_staging.doc_type = 'WebUser'
) as webusers
UNION
--- mobile users
SELECT
	domain,
	user_dim_id,
	location_dim_id,
	now(),
	now(),
	false,
	{{ batch_id }}
FROM
(
	SELECT
		user_dim.id as user_dim_id,
		user_staging.domain as domain,
		UNNEST(user_staging.assigned_location_ids) AS location_id,
		location_dim.id as location_dim_id
FROM {{ user_staging }} AS user_staging
LEFT JOIN {{ user_dim }} AS user_dim
ON user_staging.user_id = user_dim.user_id
LEFT JOIN {{ location_dim }} AS location_dim
ON location_id = location_dim.location_id
WHERE user_staging.doc_type = 'CommCareUser'
) as mobileusers;
