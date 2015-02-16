# DHIS2 API integration constants

# TODO: Get rid of all of these

ORG_UNIT_FIXTURES = 'dhis2_org_unit'

# 'child_gmp': 'Child'

NUTRITION_ASSESSMENT_PROGRAM_FIELDS = {
    # CCHQ child_gmp case attribute: DHIS2 paediatric nutrition assessment program attribute

    # c.f. http://dhis1.internal.commcarehq.org:8080/dhis/api/programs/yKSaDwadHTv.json
    #      programTrackedEntityAttributes

    'child_first_name': 'First Name',
    'child_hh_name': 'Last Name',
    'dob': 'Date of Birth',
    'child_gender': 'Gender',
    'chdr_number': 'CHDR Number',  # TODO: DHIS2 says this is optional, but throws an error if it's not passed
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

    # No relevant data elements found at http://dhis1.internal.commcarehq.org:8080/dhis/api/dataElements.json

    # DHIS2 Event: Underlying Risk
    # CCHQ form XMLNS: http://openrosa.org/formdesigner/39F09AD4-B770-491E-9255-C97B34BDD7FC Assessment
    # 'mother_id': 'Household Number',
    # 'mother_first_name': 'Name of the Mother/Guardian',
    # 'gn': 'GN Division of Household',
}

