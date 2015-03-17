# DHIS2 API integration constants

# TODO: Move all of these to per-domain config

ORG_UNIT_FIXTURES = 'dhis2_org_unit'
CCHQ_CASE_ID = 'cchq_id'
CASE_TYPE = 'child_gmp'
CASE_NAME = 'chdr_number'
TRACKED_ENTITY = 'Child'

REGISTER_CHILD_XMLNS = 'http://openrosa.org/formdesigner/6A5D0A79-E945-4F62-A737-3D4E6998685C'
GROWTH_MONITORING_XMLNS = 'http://openrosa.org/formdesigner/b6a45e8c03a6167acefcdb225ee671cbeb332a40'
RISK_ASSESSMENT_XMLNS = 'http://openrosa.org/formdesigner/39F09AD4-B770-491E-9255-C97B34BDD7FC'

NUTRITION_ASSESSMENT_PROGRAM_FIELDS = {
    # CCHQ child_gmp case attribute: DHIS2 paediatric nutrition assessment program attribute

    # c.f. http://dhis1.internal.commcarehq.org:8080/dhis/api/programs/HiHLy0f1C1q.json
    #      programTrackedEntityAttributes

    'chdr_number': 'CHDR Number',
    'child_first_name': 'First Name',
    'child_gender': 'Gender',
    'father_name': 'Last Name',
    'dob': 'Date of Birth',
    'mother_first_name': 'Name of the Mother/Guardian',
    'mother_phone_number': 'Mobile Number of the Mother',
    'street_name': 'Address',
}

NUTRITION_ASSESSMENT_EVENT_FIELDS = {
    # CCHQ form field: DHIS2 nutrition assessment event data elements

    # c.f. http://dhis1.internal.commcarehq.org:8080/dhis/api/dataElements.json

    # DHIS2 Event: Nutrition Assessment
    # CCHQ Form: Growth Monitoring
    # CCHQ form XMLNS: http://openrosa.org/formdesigner/b6a45e8c03a6167acefcdb225ee671cbeb332a40
    'child_age_months': 'Age at follow-up visit (months)',
    'child_height_rounded': 'Height (cm)',
    'child_weight': 'Weight (kg)',
    'bmi': 'Body Mass Index',
}

RISK_ASSESSMENT_PROGRAM_FIELDS = {
    # CCHQ child_gmp case attribute: DHIS2 risk assessment program attribute

    # c.f. http://dhis1.internal.commcarehq.org:8080/dhis/api/programs/rLiay0C2ZVk.json
    #      programTrackedEntityAttributes
    'mother_id': 'Household Number',
    'mother_first_name': 'Name of the Mother/Guardian',
    'gn': 'GN Division of Household',
}

RISK_ASSESSMENT_EVENT_FIELDS = {
    # CCHQ form field: DHIS2 risk assessment event data elements

    # c.f. http://dhis1.internal.commcarehq.org:8080/dhis/api/dataElements.json

    # DHIS2 Event: Underlying Risk
    # CCHQ form XMLNS: http://openrosa.org/formdesigner/39F09AD4-B770-491E-9255-C97B34BDD7FC Assessment

    # 'last_risk_assessment_date': 'Event Date',  # "Event Date" is not a DHIS2 data element

    ('causes_for_poverty', 'low_income'):
        '1.1 Low income',
    ('causes_for_poverty', 'poor_financial_management'):
        '1.2 Poor financial management',
    ('causes_for_poverty', 'limited_opportunity'):
        '1.3 Limited Opportunity for income generation within agriculture settings',
    ('causes_for_poverty', 'constrains_in_obtaining_loan'):
        '1.4 Any constrains in obtaining loan',
    ('causes_for_poverty', 'fewer_opportunities_for_occupational_trainings'):
        '1.5 Fever opportunities for occupational trainings',

    ('causes_for_inadequate_child_care', 'parent_dont_have_time'):
        '2.1 Both parents are working and do not have time to spend with children',
    ('causes_for_inadequate_child_care', 'poor_eccd_knowledge_care_givers'):
        '2.2 Poor knowledge on ECCD among care givers',
    ('causes_for_inadequate_child_care', 'poor_eccd_knowledge_serivice_providers'):
        '2.3 Poor knowledge on ECCD among service providers',
    ('causes_for_inadequate_child_care', 'unavailability_of_minimum_play_materials'):
        '2.4 Unavailability of minimum play materials',
    ('causes_for_inadequate_child_care', 'absence_of_age_appropriate_immunization'):
        '2.5 Absent of age appropriate immunization',

    ('causes_poor_feeding_practices', 'inadequate_quantity_per_meals'):
        '3.1 Inadequate quantity per meals',
    ('causes_poor_feeding_practices', 'poor_quality_of_the_meals'):
        '3.2 Poor quality of the meals',
    ('causes_poor_feeding_practices', 'inadequate_frequency_of_feeding'):
        '3.3 Inadequate frequency of feeding',
    ('causes_poor_feeding_practices', 'poor_know_nut_food_resource_utilization'):
        '3.4 Poor knowledge on obtaining nutritious food within the available resources',
    ('causes_poor_feeding_practices', 'false_believes_and_myths'):
        '3.5 False beliefs and myths',
    ('causes_poor_feeding_practices', 'poor_knowledge_of_feeding_during_illness'):
        '3.6 Poor knowledge of feeding during illness',
    ('causes_poor_feeding_practices', 'poor_knowledge_and_attitudes_towards_nutrition'):
        '3.7 Poor knowledge and attitudes towards nutrition',

    ('causes_communicable_diseases', 'respiratory_infection_frequently'):
        '4.1 Subjected to respiratory infection frequently',
    ('causes_communicable_diseases', 'diarrheal_diseases_frequently'):
        '4.2 Subjected to diarrheal diseases frequently',
    ('causes_communicable_diseases', 'frequently_fever'):
        '4.3 Subjected to fever frequently',

    ('causes_low_food_security', 'no_home_gardening'):
        '5.1 No home gardening',
    ('causes_low_food_security', 'no_consumption_of_home_foods'):
        '5.2 Non consumption of foods from home gardening or backyard farming',
    ('causes_low_food_security', 'inadequate_allocation_of_money_for_foods'):
        '5.3 Inadequate allocation of money for foods',
    ('causes_low_food_security', 'poor_harvest_from_agriculture_livestock'):
        '5.4 Poor harvest from agriculture & livestock',
    ('causes_low_food_security', 'poor_knowledge_and_attitudes_towards_food_preparation_preservation'):
        '5.5 Poor knowledge and attitude towards food presentation & preservation',
    ('causes_low_food_security', 'Inadequate_preventive_measures_for_protecting_harvest'):
        '5.6 Inadequate preventive measures for protecting harvest',
    ('causes_low_food_security', 'excessive_alcohol_or_smoking'):
        '5.7 One or both parents consuming excessive alcohol or smoking',
    ('causes_low_food_security', 'spending_higher_proportion_alcohol'):
        '5.8 Spending higher proportion of income o alcohol',
    ('causes_low_food_security', 'domestic_violence_alcohol_smoking'):
        '5.9 Domestic violence/abuse due to alcohol and smoking',

    ('causes_water_sanitation', 'unavailability_safe_water_supply'):
        '6.1 Unavailability of safe water supply',
    ('causes_water_sanitation', 'unavailability_sanitation'):
        '6.2 Unavailability of sanitation',

    ('causes_nutrition_knowledge', 'poor_knowledge_and_attitudes_nutrition'):
        '7.1 Poor knowledge & attitudes towards nutrition',
    ('causes_nutrition_knowledge', 'poor_knowledge__appropriate_food_intake'):
        '7.2 Poor knowledge on using appropriate food for family members',
    ('causes_nutrition_knowledge', 'false_believes_myths_and_customs'):
        '7.3 False believes, myths & customs',
}
