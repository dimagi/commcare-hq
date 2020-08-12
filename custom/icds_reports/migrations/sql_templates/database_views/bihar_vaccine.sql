DROP VIEW IF EXISTS bihar_vaccine_view CASCADE;
CREATE VIEW bihar_vaccine_view AS
    SELECT
        "bihar_demographics"."month" AS "month",
        "bihar_demographics"."person_id" AS "person_id",
        "bihar_demographics"."state_id" AS "state_id",
        "bihar_demographics"."supervisor_id" AS "supervisor_id",
        "bihar_demographics"."time_birth" AS "time_birth",
        "bihar_demographics"."child_alive" AS "child_alive",
        "bihar_demographics"."father_name" AS "father_name",
        "bihar_demographics"."mother_name" AS "mother_name",
        "bihar_demographics"."father_id" AS "father_id",
        "child_health"."mother_case_id" AS "mother_id",
        "child_health"."delivery_nature" AS "delivery_nature",
        CASE WHEN "child_health"."term_days" > 0 THEN "child_health"."term_days" ELSE NULL END AS term_days,
        "child_health"."birth_weight" AS "birth_weight",
        "bihar_demographics"."dob" AS "dob",
        "bihar_demographics"."household_id" AS "household_id",
        "bihar_demographics"."private_admit" AS "private_admit",
        "bihar_demographics"."primary_admit" AS "primary_admit",
        "bihar_demographics"."date_last_private_admit" AS "date_last_private_admit",
        "bihar_demographics"."date_return_private" AS "date_return_private",
        "bihar_demographics"."last_reported_fever_date" AS "last_reported_fever_date",
        "child_vaccines"."due_list_date_1g_dpt_1" as "due_list_date_1g_dpt_1",
        "child_vaccines"."due_list_date_2g_dpt_2" as "due_list_date_2g_dpt_2",
        "child_vaccines"."due_list_date_3g_dpt_3" as "due_list_date_3g_dpt_3",
        "child_vaccines"."due_list_date_5g_dpt_booster" as "due_list_date_5g_dpt_booster",
        "child_vaccines"."due_list_date_7gdpt_booster_2" as "due_list_date_7gdpt_booster_2",
        "child_vaccines"."due_list_date_0g_hep_b_0" as "due_list_date_0g_hep_b_0",
        "child_vaccines"."due_list_date_1g_hep_b_1" as "due_list_date_1g_hep_b_1",
        "child_vaccines"."due_list_date_2g_hep_b_2" as "due_list_date_2g_hep_b_2",
        "child_vaccines"."due_list_date_3g_hep_b_3" as "due_list_date_3g_hep_b_3",
        "child_vaccines"."due_list_date_3g_ipv" as "due_list_date_3g_ipv",
        "child_vaccines"."due_list_date_4g_je_1" as "due_list_date_4g_je_1",
        "child_vaccines"."due_list_date_5g_je_2" as "due_list_date_5g_je_2",
        "child_vaccines"."due_list_date_5g_measles_booster" as "due_list_date_5g_measles_booster",
        "child_vaccines"."due_list_date_4g_measles" as "due_list_date_4g_measles",
        "child_vaccines"."due_list_date_0g_opv_0" as "due_list_date_0g_opv_0",
        "child_vaccines"."due_list_date_1g_opv_1" as "due_list_date_1g_opv_1",
        "child_vaccines"."due_list_date_2g_opv_2" as "due_list_date_2g_opv_2",
        "child_vaccines"."due_list_date_3g_opv_3" as "due_list_date_3g_opv_3",
        "child_vaccines"."due_list_date_5g_opv_booster" as "due_list_date_5g_opv_booster",
        "child_vaccines"."due_list_date_1g_penta_1" as "due_list_date_1g_penta_1",
        "child_vaccines"."due_list_date_2g_penta_2" as "due_list_date_2g_penta_2",
        "child_vaccines"."due_list_date_3g_penta_3" as "due_list_date_3g_penta_3",
        "child_vaccines"."due_list_date_1g_rv_1" as "due_list_date_1g_rv_1",
        "child_vaccines"."due_list_date_2g_rv_2" as "due_list_date_2g_rv_2",
        "child_vaccines"."due_list_date_3g_rv_3" as "due_list_date_3g_rv_3",
        "child_vaccines"."due_list_date_4g_vit_a_1" as "due_list_date_4g_vit_a_1",
        "child_vaccines"."due_list_date_5g_vit_a_2" as "due_list_date_5g_vit_a_2",
        "child_vaccines"."due_list_date_6g_vit_a_3" as "due_list_date_6g_vit_a_3",
        "child_vaccines"."due_list_date_6g_vit_a_4" as "due_list_date_6g_vit_a_4",
        "child_vaccines"."due_list_date_6g_vit_a_5" as "due_list_date_6g_vit_a_5",
        "child_vaccines"."due_list_date_6g_vit_a_6" as "due_list_date_6g_vit_a_6",
        "child_vaccines"."due_list_date_6g_vit_a_7" as "due_list_date_6g_vit_a_7",
        "child_vaccines"."due_list_date_6g_vit_a_8" as "due_list_date_6g_vit_a_8",
        "child_vaccines"."due_list_date_7g_vit_a_9" as "due_list_date_7g_vit_a_9",
        "child_vaccines"."due_list_date_1g_bcg" as "due_list_date_1g_bcg"

    FROM "public"."child_health_monthly" "child_health"
    LEFT JOIN "public"."child_vaccines" "child_vaccines"
    ON (
        ("child_health"."supervisor_id" = "child_vaccines"."supervisor_id") AND
        ("child_health"."case_id" = "child_vaccines"."child_health_case_id") AND
        ("child_health"."month" = "child_vaccines"."month")
    )
    INNER JOIN "public"."bihar_api_demographics" "bihar_demographics"
    ON (
        ("child_health"."supervisor_id" = "bihar_demographics"."supervisor_id") AND
        ("child_health"."child_person_case_id" = "bihar_demographics"."person_id") AND
        ("child_health"."month" = "bihar_demographics"."month")

    );
