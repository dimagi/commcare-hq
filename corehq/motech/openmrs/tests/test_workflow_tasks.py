from django.test import SimpleTestCase

from testil import eq

from corehq.motech.openmrs.openmrs_config import (
    ALL_CONCEPTS,
    OpenmrsConfig,
    OpenmrsFormConfig,
)
from corehq.motech.openmrs.workflow_tasks import (
    CreateVisitsEncountersObsTask,
    get_values_for_concept,
)
from corehq.motech.value_source import CaseTriggerInfo


def test_concept_directions():
    form_json = {
        "form": {
            "@xmlns": "http://openrosa.org/formdesigner/9ECA0608-307A-4357-954D-5A79E45C3879",
            "pneumonia": "no",
            "malnutrition": "no",
        }
    }
    form_config_dict = get_form_config_dict()
    form_config = form_config_dict
    info = CaseTriggerInfo(
        domain="test-domain",
        case_id="c0ffee",
        form_question_values={
            "/data/pneumonia": "no",
            "/data/malnutrition": "no",
        }
    )
    task = get_task(info, form_json, form_config_dict)
    values_for_concepts = get_values_for_concept(form_config, task.info)
    eq(values_for_concepts, {
        # "direction": "out"
        'e7fdcd25-6d11-4d85-a80a-8979785f0f4b': ['eea8e4e9-4a91-416c-b0f5-ef0acfbc51c0'],
        # "direction": null, or not specified
        '4000cf24-8fab-437d-9950-ea8d9bb05a09': ['eea8e4e9-4a91-416c-b0f5-ef0acfbc51c0'],
        # "direction": "in" should be missing
    })


def test_start_stop_datetime_export():
    form_config_dict = get_form_config_dict()
    form_config_dict["openmrs_start_datetime"] = {
        "form_question": "/data/visit_datetime",
        "external_data_type": "omrs_datetime",
    }
    form_json = {
        "form": {
            "@xmlns": "http://openrosa.org/formdesigner/9ECA0608-307A-4357-954D-5A79E45C3879",
            "visit_datetime": "2018-01-01T12:00:00.00000Z",
            "meta": {"timeEnd": "2019-12-16T12:36:00.00000Z"},
        }
    }
    info = CaseTriggerInfo(
        domain="test-domain",
        case_id="c0ffee",
        form_question_values={
            "/data/visit_datetime": "2018-01-01T12:00:00.00000Z",
            "/metadata/timeEnd": "2019-12-16T12:36:00.00000Z",
        }
    )
    task = get_task(info, form_json, form_config_dict)
    start_datetime, stop_datetime = task._get_start_stop_datetime(
        form_config_dict
    )
    eq(start_datetime, "2018-01-01T12:00:00.000+0000")
    eq(stop_datetime, "2018-01-02T11:59:59.000+0000")


def test_start_stop_datetime_import():
    form_config_dict = get_form_config_dict()
    form_config_dict['openmrs_start_datetime'] = {
        "direction": "in",
        "case_property": "ehr_last_visit_date",
        "external_data_type": "omrs_datetime",
        "commcare_data_type": "cc_date",
        "jsonpath": "encounterDateTime",
    }
    form_json = {
        "form": {
            "@xmlns": "http://openrosa.org/formdesigner/9ECA0608-307A-4357-954D-5A79E45C3879",
            "meta": {"timeEnd": "2019-12-16T12:36:00.00000Z"},
        }
    }
    info = CaseTriggerInfo(domain="test-domain", case_id="c0ffee")
    task = get_task(info, form_json, form_config_dict)
    start_datetime, stop_datetime = task._get_start_stop_datetime(
        OpenmrsFormConfig.wrap(form_config_dict)
    )
    eq(start_datetime, "2019-12-16T12:36:00.000+0000")
    eq(stop_datetime, "2019-12-17T12:35:59.000+0000")


class GetValuesForConceptTests(SimpleTestCase):

    def test_get_values_for_all_concepts(self):
        form_config = {
            "openmrs_observations": [{
                "concept": ALL_CONCEPTS
            }]
        }
        info = CaseTriggerInfo(domain="test-domain", case_id="c0ffee")
        values_for_concept = get_values_for_concept(form_config, info)
        self.assertEqual(values_for_concept, {})

    def test_get_values_for_different_concepts(self):
        form_config = {
            "openmrs_observations": [
                {
                    "concept": "123456",
                    "value": {"form_question": "/data/symptoms/fever"}
                },
                {
                    "concept": "789abc",
                    "value": {"form_question": "/data/symptoms/vomiting"}
                },
                {
                    "concept": "def012",
                    "value": {"form_question": "/data/symptoms/diarrhea"}
                },
            ]
        }
        info = CaseTriggerInfo(
            domain="test-domain",
            case_id="c0ffee",
            form_question_values={
                "/data/symptoms/fever": True,
                "/data/symptoms/vomiting": True,
                "/data/symptoms/diarrhea": True,
            }
        )
        values_for_concept = get_values_for_concept(form_config, info)
        self.assertEqual(values_for_concept, {
            "123456": [True],
            "789abc": [True],
            "def012": [True],
        })

    def test_get_values_for_the_same_concept(self):
        form_config = {
            "openmrs_observations": [
                {
                    "concept": "123456",
                    "value": {"form_question": "/data/symptoms/fever"}
                },
                {
                    "concept": "123456",
                    "value": {"form_question": "/data/symptoms/vomiting"}
                },
                {
                    "concept": "123456",
                    "value": {"form_question": "/data/symptoms/diarrhea"}
                },
            ]
        }
        info = CaseTriggerInfo(
            domain="test-domain",
            case_id="c0ffee",
            form_question_values={
                "/data/symptoms/fever": True,
                "/data/symptoms/vomiting": True,
                "/data/symptoms/diarrhea": True,
            }
        )
        values_for_concept = get_values_for_concept(form_config, info)
        self.assertEqual(values_for_concept, {"123456": [True, True, True]})

    def test_get_values_for_import_concept(self):
        form_config = {
            "openmrs_observations": [{
                "concept": "123456",
                "value": {
                    "case_property": "has_fever",
                    "direction": "in",
                }
            }]
        }
        info = CaseTriggerInfo(domain="test-domain", case_id="c0ffee")
        values_for_concept = get_values_for_concept(form_config, info)
        self.assertEqual(values_for_concept, {})


def get_form_config_dict():
    return {
        "xmlns": "http://openrosa.org/formdesigner/9ECA0608-307A-4357-954D-5A79E45C3879",
        "openmrs_visit_type": "c23d6c9d-3f10-11e4-adec-0800271c1b75",
        "openmrs_encounter_type": "81852aee-3f10-11e4-adec-0800271c1b75",
        "openmrs_observations": [
            {
                "doc_type": "ObservationMapping",
                "concept": "e7fdcd25-6d11-4d85-a80a-8979785f0f4b",
                "value": {
                    "form_question": "/data/pneumonia",
                    "doc_type": "FormQuestionMap",
                    "value_map": {
                        "yes": "05ced69b-0790-4aad-852f-ba31fe82fbd9",
                        "no": "eea8e4e9-4a91-416c-b0f5-ef0acfbc51c0",
                    },
                    "direction": "out",
                },
                "case_property": None,
            },
            {
                "doc_type": "ObservationMapping",
                "concept": "4000cf24-8fab-437d-9950-ea8d9bb05a09",
                "value": {
                    "form_question": "/data/malnutrition",
                    "doc_type": "FormQuestionMap",
                    "value_map": {
                        "yes": "05ced69b-0790-4aad-852f-ba31fe82fbd9",
                        "no": "eea8e4e9-4a91-416c-b0f5-ef0acfbc51c0",
                    },
                    # direction defaults to null, for both import and export
                },
                "case_property": "malnutrition",
            },
            {
                "doc_type": "ObservationMapping",
                "concept": "724a5cb9-3826-4fe0-bc0d-0a8e9d9c4c42",
                "value": {
                    "doc_type": "ConstantValue",
                    "direction": "in",
                    "value": "Fever, unspecified",
                    "value_data_type": "cc_text",
                },
                "case_property": "ehr_fever_unspecified",
            },
        ],
    }


def get_task(info, form_json, form_config_dict):
    return CreateVisitsEncountersObsTask(
        requests=None,
        domain="test-domain",
        info=info,
        form_json=form_json,
        openmrs_config=OpenmrsConfig.wrap({
            "case_config": {},
            "form_configs": [form_config_dict],
        }).to_json(),
        person_uuid="test-person_uuid",
    )
