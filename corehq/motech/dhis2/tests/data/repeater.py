dhis2_entity_repeater_data = {
    "dhis2_entity_config":
    {
        "case_configs":
        [
            {
                "doc_type": "Dhis2CaseConfig",
                "case_type": "cps",
                "te_type_id": "Vz4rOPQJPHW",
                "tei_id":
                {
                    "case_property": "dhis2_tei_id"
                },
                "org_unit_id":
                {
                    "value": "QVRHaVvDQgD"
                },
                "attributes":
                {
                    "L94Yck2opZn":
                    {
                        "case_property": "first_name"
                    },
                    "AAEYzp0EvHi":
                    {
                        "case_property": "last_name"
                    },
                    "v3bPqw4oA6O":
                    {
                        "case_property": "gender"
                    },
                    "f3VOrC9HBOm":
                    {
                        "case_property": "child_age"
                    },
                    "uE8D2CincNr":
                    {
                        "case_property": "mother_name"
                    }
                },
                "finder_config":
                {
                    "property_weights":
                    [
                        {
                            "case_property": "first_name",
                            "weight": "0.35",
                            "match_type": "exact",
                            "match_params":
                            [],
                            "doc_type": "PropertyWeight"
                        },
                        {
                            "case_property": "last_name",
                            "weight": "0.55",
                            "match_type": "exact",
                            "match_params":
                            [],
                            "doc_type": "PropertyWeight"
                        },
                        {
                            "case_property": "child_age",
                            "weight": "0.1",
                            "match_type": "exact",
                            "match_params":
                            [],
                            "doc_type": "PropertyWeight"
                        }
                    ],
                    "confidence_margin": "0.5",
                    "doc_type": "FinderConfig"
                },
                "form_configs":
                [
                    {
                        "doc_type": "Dhis2FormConfig",
                        "xmlns": "http://openrosa.org/formdesigner/69A0067F-B757-4EDB-B1FF-470D3BCA3F15",
                        "program_id": "Jz69xPyCQtD",
                        "program_stage_id":
                        {
                            "value": "YWXud3jESes"
                        },
                        "org_unit_id":
                        {
                            "value": "QVRHaVvDQgD"
                        },
                        "program_status":
                        {
                            "value": "ACTIVE"
                        },
                        "event_status":
                        {
                            "value": "ACTIVE"
                        },
                        "datavalue_maps":
                        [
                            {
                                "data_element_id": "XcZFbXk5dqH",
                                "value":
                                {
                                    "form_question": "/data/treatment_provided"
                                },
                                "doc_type": "FormDataValueMap"
                            },
                            {
                                "data_element_id": "OWJwRcDOgzx",
                                "value":
                                {
                                    "form_question": "/data/side_effects"
                                },
                                "doc_type": "FormDataValueMap"
                            }
                        ],
                        "enrollment_date":
                        {},
                        "incident_date":
                        {},
                        "event_date":
                        {
                            "form_question": "/metadata/received_on",
                            "external_data_type": "dhis2_date"
                        },
                        "completed_date":
                        {},
                        "event_location":
                        {}
                    }
                ],
                "relationships_to_export":
                []
            }
        ],
        "doc_type": "Dhis2EntityConfig"
    },
    "repeater_type": "Dhis2EntityRepeater",
    "version": "2.0",
    "white_listed_case_types":
    [],
    "black_listed_users":
    [],
    "format": "form_json",
    "is_paused": False,
    "dhis2_version": "2.33.9",
    "dhis2_version_last_modified": "2021-11-08T15:56:10.854630Z"
}

dhis2_repeater_data = {
    "dhis2_config":
    {
        "doc_type": "Dhis2Config",
        "form_configs":
        [
            {
                "doc_type": "Dhis2FormConfig",
                "xmlns": "http://openrosa.org/formdesigner/3974C41B-0BC4-4B27-B6D2-6FE49E33D961",
                "datavalue_maps":
                [
                    {
                        "data_element_id": "S9zdlWB1xny",
                        "value":
                        {
                            "doc_type": "FormQuestion",
                            "form_question": "/data/dhis2_indicators/dhis2_avortement_bovin_ovin_caprin"
                        },
                        "doc_type": "FormDataValueMap"
                    },
                    {
                        "data_element_id": "ENxf6cfFlFR",
                        "categoryOptionCombo": "iaUZ0KXio4m",
                        "value":
                        {
                            "doc_type": "FormQuestion",
                            "form_question": "/data/dhis2_indicators/dhis2_suscption_rougeole_mort"
                        },
                        "doc_type": "FormDataValueMap"
                    },
                    {
                        "data_element_id": "VOpvrwKrAoJ",
                        "value":
                        {
                            "doc_type": "FormQuestion",
                            "form_question": "/data/dhis2_indicators/dhis2_mention_particuliere"
                        },
                        "doc_type": "FormDataValueMap"
                    }
                ],
                "org_unit_id":
                {
                    "location_field": "org_unit_id_simr",
                    "doc_type": "FormUserAncestorLocationField"
                },
                "program_id": "lasd4I6jsbl",
                "event_status":
                {
                    "value": "COMPLETED"
                },
                "dataSet": "WEu0IGoo8mU",
                "completeDate":
                {
                    "form_question": "/data/dhis2_indicators/dates_calc/date",
                    "doc_type": "FormQuestion"
                },
                'event_location': {},
                "period":
                {
                    "form_question": "/data/dhis2_indicators/dhis2_real_date",
                    "doc_type": "FormQuestion"
                },
                "event_date":
                {
                    "form_question": "/data/dhis2_indicators/dhis2_real_date",
                    "doc_type": "FormQuestion"
                },
                "completed_date": None,
                "enrollment_date":
                {},
                "incident_date":
                {},
                "program_stage_id":
                {},
                "program_status":
                {
                    "value": "ACTIVE"
                }
            }
        ]
    },
    "format": "form_json",
    "is_paused": False,
    "repeater_type": "Dhis2Repeater",
    "white_listed_form_xmlns":
    [],
    "dhis2_version": None,
    "dhis2_version_last_modified": None,
}
