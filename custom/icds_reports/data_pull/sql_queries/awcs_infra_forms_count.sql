SELECT state_name,
       Sum(num_awc_infra_last_update)           AS "# of AWCs that submitted Infra form",
       Sum(cases_household)                     AS "# Households Registered",
       Sum(cases_ccs_pregnant)                  AS "# Pregnant Women",
       Sum(cases_ccs_lactating)                 AS "# Lactating Mothers",
       Sum(cases_person_adolescent_girls_11_14) AS "# Adolescent Girls (11-14y)",
       Sum(cases_child_health)                  AS "# Children (0-6y)"
FROM   agg_awc_monthly
WHERE  aggregation_level = 1
       AND month = '{month}'
GROUP  BY state_name
