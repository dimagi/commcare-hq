test_data = {
    "location_id": "581fe9d38a2c4eaf8e1fee1420800118",
    "openmrs_config":
    {
        "openmrs_provider": "35711912-13A6-47F9-8D54-655FCAD75895",
        "case_config":
        {
            "patient_identifiers":
            {
                "uuid":
                {
                    "case_property": "external_id"
                }
            },
            "match_on_ids":
            [
                "uuid"
            ],
            "person_properties":
            {},
            "person_preferred_name":
            {},
            "person_preferred_address":
            {},
            "person_attributes":
            {},
            "doc_type": "OpenmrsCaseConfig",
            "import_creates_cases": False
        },
        "form_configs":
        [
            {
                "__form_name__": "prenatal",
                "doc_type": "OpenmrsFormConfig",
                "xmlns": "http://openrosa.org/formdesigner/00822D7D-D6B9-4F02-9067-02AAEA49436F",
                "openmrs_visit_type": "90973824-1AE9-4E22-B2BB-9CBD56FB3238",
                "openmrs_observations":
                [
                    {
                        "doc_type": "ObservationMapping",
                        "concept": "3ce934fa-26fe-102b-80cb-0017a47871b2",
                        "value":
                        {
                            "form_question": "/data/signes_vitaux_de_la_mre/TA_Systolique"
                        },
                        "case_property": None
                    },
                    {
                        "doc_type": "ObservationMapping",
                        "concept": "3ce93694-26fe-102b-80cb-0017a47871b2",
                        "value":
                        {
                            "form_question": "/data/signes_vitaux_de_la_mre/ta_diastolique"
                        },
                        "case_property": None
                    },
                    {
                        "doc_type": "ObservationMapping",
                        "concept": "3ce939d2-26fe-102b-80cb-0017a47871b2",
                        "value":
                        {
                            "form_question": "/data/signes_vitaux_de_la_mre/temp-maternel"
                        },
                        "case_property": None
                    },
                    {
                        "doc_type": "ObservationMapping",
                        "concept": "3cd95a58-26fe-102b-80cb-0017a47871b2",
                        "value":
                        {
                            "form_question": "/data/signes_durgence_de_la_mre/passage_de_liquide",
                            "value_map":
                            {
                                "oui": "148968AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
                            }
                        },
                        "case_property": None
                    },
                    {
                        "doc_type": "ObservationMapping",
                        "concept": "164141AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                        "value":
                        {
                            "form_question": "/metadata/username"
                        },
                        "case_property": None
                    }
                ],
                "openmrs_start_datetime":
                {
                    "form_question": "/data/maternel/date_visite_domicile",
                    "external_data_type": "omrs_date"
                },
                "openmrs_encounter_type": "91DDF969-A2D4-4603-B979-F2D6F777F4AF",
                "openmrs_form": None,
                "bahmni_diagnoses":
                []
            },
        ],
        "doc_type": "OpenmrsConfig"
    },
    "atom_feed_enabled": True,
    "atom_feed_status": {
        'patient': {
            'last_polled_at': '2022-06-01T00:00:00.000000Z',
            'last_page': None,
            'doc_type': 'AtomFeedStatus'
        }
    },
    "version": "2.0",
    "white_listed_case_types":
    [
        "patient"
    ],
    "black_listed_users":
    [],
    "format": "form_json",
    "is_paused": False,
}
