import json

from testil import assert_raises, eq

from corehq.form_processor.utils import convert_xform_to_json

from ..json2xml import (
    RoundtripError,
    convert_form_to_xml,
)


def test_convert_form_to_xml():
    json_to_xml_to_json(TEST_FORM_JSON)


def test_simple_form():
    json_to_xml_to_json(SIMPLE_FORM_JSON)


def test_iteration_form():
    json_to_xml_to_json(JURY_ITERATION_FORM_JSON)


def test_validation_failure():
    form_data = json.loads(TEST_FORM_JSON)
    form_data["#text"] = None
    msg = "to_json(to_xml(form_data)) != form_data"
    with assert_raises(RoundtripError, msg=msg):
        convert_form_to_xml(form_data)


def json_to_xml_to_json(form_json):
    form_data = json.loads(form_json)
    xml = convert_form_to_xml(form_data)
    print(xml)
    eq(convert_xform_to_json(xml), form_data)


TEST_FORM_JSON = """{
    "@name": "Registration",
    "@uiVersion": "1",
    "@version": "11",
    "@xmlns": "http://openrosa.org/formdesigner/test-form",
    "first_name": "Xeenax",
    "age": "27",
    "case": {
        "@case_id": "test-case",
        "@date_modified": "2015-08-04T18:25:56.656000Z",
        "@user_id": "3fae4ea4af440efaa53441b5",
        "@xmlns": "http://commcarehq.org/case/transaction/v2",
        "create": {
            "case_name": "Xeenax",
            "owner_id": "3fae4ea4af440efaa53441b5",
            "case_type": "testing"
        },
        "update": {
            "age": "27"
        }
    },
    "meta": {
        "@xmlns": "http://openrosa.org/jr/xforms",
        "deviceID": "cloudcare",
        "timeStart": "2015-07-13T11:20:11.381000Z",
        "timeEnd": "2015-08-04T18:25:56.656000Z",
        "username": "jeremy",
        "userID": "3fae4ea4af440efaa53441b5",
        "instanceID": "test-form",
        "appVersion": {
            "@xmlns": "http://commcarehq.org/xforms",
            "#text": "2.0"
        }
    },
    "#type": "data"
}"""

SIMPLE_FORM_JSON = """{
    "@xmlns": "http://openrosa.org/user/registration",
    "username": "W4",
    "password": "2",
    "uuid": "P8DU7OLHVLZXU21JR10H3W8J2",
    "date": "2013-11-19",
    "registering_phone_id": "8H1N48EFPF6PA4UOO8YGZ2KFZ",
    "user_data": {
        "data": {
            "@key": "user_type",
            "#text": "standard"
        }
    },
    "#type": "registration"
}"""

JURY_ITERATION_FORM_JSON = ("""{
    "#type": "data",
    "@name": "Jury Selection",
    "@uiVersion": "1",
    "@version": "2118",
    "@xmlns": "http://openrosa.org/formdesigner/scopesmonkey",
    "case_case_juror": {
        "case": {
            "@case_id": "cf468f9a-cf80-474b-b815-d98c5b15c906",
            "@date_modified": "2016-08-04T11:10:13.968000Z",
            "@user_id": "6b2c8e5248d41c86c387fcd4041d40fc",
            "@xmlns": "http://commcarehq.org/case/transaction/v2",
            "update": {
                "jury_selection": "completed"
            }
        }
    },
    "case_case_visit": {
        "case": {
            "@case_id": "79c77f8d-d528-41aa-b472-6034030bf3b9",
            "@date_modified": "2016-08-04T11:10:13.968000Z",
            "@user_id": "e4b86f265be4cd1e952077970a792470",
            "@xmlns": "http://commcarehq.org/case/transaction/v2",
            "update": {
                "jury_selection": "completed"
            }
        }
    },
    "jury_calculation": {
        "iterate_over_members": {
            "@count": "4",
            "@current_index": "4",
            "@ids": "900bed221e0ca7ab2c291f1dbf643757 3cda01767a7241d07a01610c361d8550 """
                    """45e09c95bd32f81f5449e90aa4320cdc fccc3c3a7b6406e37847eebf4cfd7603",
            "item": [
                {
                    "@id": "900bed221e0ca7ab2c291f1dbf643757",
                    "@index": "0",
                    "need_to_multiply_by_weight": "yes",
                    "prescribed_question": "-153000",
                    "prescribed_answer": "Darrow De Lysine",
                    "raw_question": "150"
                },
                {
                    "@id": "3cda01767a7241d07a01610c361d8550",
                    "@index": "1",
                    "need_to_multiply_by_weight": "yes",
                    "prescribed_question": "-153000",
                    "prescribed_answer": "McKenzie De Lysine",
                    "raw_question": "150"
                },
                {
                    "@id": "45e09c95bd32f81f5449e90aa4320cdc",
                    "@index": "82",
                    "need_to_multiply_by_weight": "yes",
                    "prescribed_question": "-153000",
                    "prescribed_answer": "Paracétamol Oral",
                    "raw_question": "150",
                    "transfer": {
                        "@date": "",
                        "@section-id": "prescribed_stat",
                        "@src": "64c09c0e-d13f-47f6-b2aa-21cb7f6eb8d7",
                        "@type": "write_prescribed_stat_to_ledger_juror",
                        "@xmlns": "http://commcarehq.org/ledger/v1",
                        "entry": {
                            "@id": "45e09c95bd32f81f5449e90aa4320cdc",
                            "@quantity": "-153000"
                        }
                    }
                },
                {
                    "@id": "fccc3c3a7b6406e37847eebf4cfd7603",
                    "@index": "134",
                    "need_to_multiply_by_weight": "no",
                    "prescribed_question": "-500",
                    "prescribed_answer": "Vitamine A - Capsules 200'000 UI",
                    "raw_question": "5"
                }
            ]
        }
    },
    "debug": "0",
    "label_prescription_ready": "OK",
    "stat": {
        "all_antibios_choosen": "  ",
        "count_all": "2",
        "count_antibio": "0"
    },
    "jury_selection": "completed",
    "meta": {
        "@xmlns": "http://openrosa.org/jr/xforms",
        "appVersion": {
            "#text": "CommCare Android, version \\"2.27.2\\"(414569). """
                    """App v2653. CommCare Version 2.27. Build 414569, built on: 2016-04-28",
            "@xmlns": "http://commcarehq.org/xforms"
        },
        "deviceID": "32f81f5449e90",
        "instanceID": "17fe44ab-8128-43d3-8862-a34b85c311b2",
        "timeEnd": "2016-08-04T11:10:13.968000Z",
        "timeStart": "2016-08-04T11:10:02.943000Z",
        "userID": "7b4c5f2cbd79c5554f23d738321b72f9",
        "username": "deuty"
    },
    "possible_stat": {
        "look_for_rejection_of_same_class": {
            "@count": "5",
            "@current_index": "5",
            "@ids": "a17976038b90b9d87c78909257a1ba80 """
                    """45e09c95bd32f81f5449e90aa4320cdc 4fb193b4e49bd1cb7bbf870273862dd2 """
                    """4743e31168427f26cdbcba47c600ed1a 86763570a848b51810f339f90d5cd1cd",
            "item": [
                {
                    "@id": "a17976038b90b9d87c78909257a1ba80",
                    "@index": "0",
                    "all_stat": "a17976038b90b9d87c78909257a1ba80",
                    "artemether_id": "a17976038b90b9d87c78909257a1ba80"
                },
                {
                    "@id": "45e09c95bd32f81f5449e90aa4320cdc",
                    "@index": "1",
                    "all_stat": "45e09c95bd32f81f5449e90aa4320cdc",
                    "stat_that_dont_need_reconciliation": "45e09c95bd32f81f5449e90aa4320cdc"
                },
                {
                    "@id": "4fb193b4e49bd1cb7bbf870273862dd2",
                    "@index": "2",
                    "all_stat": "4fb193b4e49bd1cb7bbf870273862dd2",
                    "artemether_id": "4fb193b4e49bd1cb7bbf870273862dd2"
                },
                {
                    "@id": "4743e31168427f26cdbcba47c600ed1a",
                    "@index": "3",
                    "all_stat": "4743e31168427f26cdbcba47c600ed1a",
                    "vitamine_a_id_option": "4743e31168427f26cdbcba47c600ed1a"
                },
                {
                    "@id": "86763570a848b51810f339f90d5cd1cd",
                    "@index": "4",
                    "all_stat": "86763570a848b51810f339f90d5cd1cd",
                    "vitamine_a_id_option": "86763570a848b51810f339f90d5cd1cd"
                }
            ]
        }
    },
    "select_stat": {
        "all_antibio": "",
        "all_antibio_option": "",
        "all_artemether": "a17976038b90b9d87c78909257a1ba80 4fb193b4e49bd1cb7bbf870273862dd2",
        "all_artemether_option": "",
        "all_chosen_med_ids": "45e09c95bd32f81f5449e90aa4320cdc a17976038b90b9d87c78909257a1ba80",
        "all_classless_stat": "45e09c95bd32f81f5449e90aa4320cdc",
        "all_deparasitage": "",
        "all_deparasitage_option": "",
        "all_perfusion_p1_a": "",
        "all_perfusion_p1_b": "",
        "all_perfusion_p2_a": "",
        "all_perfusion_p2_b": "",
        "all_vitamine_a_option": "4743e31168427f26cdbcba47c600ed1a 86763570a848b51810f339f90d5cd1cd",
        "artemether": "a17976038b90b9d87c78909257a1ba80",
        "list_of_stat_not_needing_selection": "            45e09c95bd32f81f5449e90aa4320cdc"
    },
    "visit_type_loaded": "imci_juror",
    "vitamin_a_loaded": "yes",
    "weight_loaded": "10.2"
}""")
