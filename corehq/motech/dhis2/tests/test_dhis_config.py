
import json
import six

from django.test import SimpleTestCase
from fakecouch import FakeCouchDb
from jsonobject.base_properties import BadValueError

from corehq.motech.dhis2.dhis2_config import Dhis2Config
from corehq.motech.dhis2.forms import Dhis2ConfigForm
from corehq.motech.dhis2.repeaters import Dhis2Repeater


class TestDhisConfigValidation(SimpleTestCase):

    def setUp(self):
        self.db = Dhis2Repeater.get_db()
        self.fakedb = FakeCouchDb()
        Dhis2Repeater.set_db(self.fakedb)

    def tearDown(self):
        Dhis2Repeater.set_db(self.db)

    def test_form_validation(self):
        config = {
            'form_configs': [{}]
        }
        form = Dhis2ConfigForm(data=config)
        self.assertFalse(form.is_valid())
        self.assertDictEqual(form.errors, {
            'form_configs': [
                'The "program_id" property is required. Please specify the DHIS2 Program of the event.',
                'The "event_date" property is required. Please provide a FormQuestion, FormQuestionMap or '
                'ConstantString to determine the date of the event.',
                'The "datavalue_maps" property is required. Please map CommCare values to OpenMRS data elements.'
            ]
        })

    def test_empty_json(self):
        config = {
            'form_configs': [{}]
        }
        repeater = Dhis2Repeater()
        repeater.dhis2_config = Dhis2Config.wrap(config)
        with self.assertRaises(BadValueError) as e:
            repeater.save()
        self.assertEqual(
            six.text_type(e.exception),
            "Property program_id is required."
        )

    def test_missing_event_date(self):
        config = {
            'form_configs': [{
                'program_id': 'test program'
            }]
        }
        repeater = Dhis2Repeater()
        repeater.dhis2_config = Dhis2Config.wrap(config)
        with self.assertRaises(BadValueError) as e:
            repeater.save()
        self.assertEqual(
            six.text_type(e.exception),
            'Property event_date is required.'
        )

    def test_minimal_config(self):
        config = {
            'form_configs': json.dumps([{
                'program_id': 'test program',
                'event_date': {
                    'doc_type': 'FormQuestion',
                    'form_question': '/data/event_date'
                },
                'datavalue_maps': [
                    {
                        'data_element_id': 'dhis2_element_id',
                        'value': {
                            'doc_type': 'FormQuestion',
                            'form_question': '/data/example_question'
                        }
                    }
                ]
            }])
        }
        form = Dhis2ConfigForm(data=config)
        self.assertTrue(form.is_valid())

        repeater = Dhis2Repeater()
        repeater.dhis2_config = Dhis2Config.wrap(form.cleaned_data)
        repeater.save()

    def test_config_empty_datavalue_map(self):
        config = {
            'form_configs': json.dumps([{
                'xmlns': 'test_xmlns',
                'program_id': 'test program',
                'event_date': {
                    'doc_type': 'FormQuestion',
                    'form_question': '/data/event_date'
                },
                'event_status': 'COMPLETED',
                'org_unit_id': {
                    'doc_type': 'ConstantString',
                    'value': 'dhis2_location_id'
                },
                'datavalue_maps': [
                    {}
                ]
            }])
        }
        form = Dhis2ConfigForm(data=config)
        self.assertTrue(form.is_valid())

        repeater = Dhis2Repeater()
        repeater.dhis2_config = Dhis2Config.wrap(form.cleaned_data)
        with self.assertRaises(BadValueError) as e:
            repeater.save()
        self.assertEqual(
            six.text_type(e.exception),
            "Property data_element_id is required."
        )

    def test_full_config(self):
        config = {
            'form_configs': json.dumps([{
                'xmlns': 'test_xmlns',
                'program_id': 'test program',
                'event_date': {
                    'doc_type': 'FormQuestion',
                    'form_question': '/data/event_date'
                },
                'event_status': 'COMPLETED',
                'org_unit_id': {
                    'doc_type': 'ConstantString',
                    'value': 'dhis2_location_id'
                },
                'datavalue_maps': [
                    {
                        'data_element_id': 'dhis2_element_id',
                        'value': {
                            'doc_type': 'FormQuestion',
                            'form_question': '/data/example_question'
                        }
                    }
                ]
            }])
        }
        form = Dhis2ConfigForm(data=config)
        self.assertTrue(form.is_valid())

        repeater = Dhis2Repeater()
        repeater.dhis2_config = Dhis2Config.wrap(form.cleaned_data)
        repeater.save()

    def test_org_unit_id_migration(self):
        config = {
            'form_configs': json.dumps([{
                'program_id': 'test program',
                'org_unit_id': 'dhis2_location_id',
                'event_date': {
                    'doc_type': 'FormQuestion',
                    'form_question': '/data/event_date'
                },
                'datavalue_maps': [
                    {
                        'data_element_id': 'dhis2_element_id',
                        'value': {
                            'doc_type': 'FormQuestion',
                            'form_question': '/data/example_question'
                        }
                    }
                ]
            }])
        }
        form = Dhis2ConfigForm(data=config)
        self.assertTrue(form.is_valid())

        repeater = Dhis2Repeater()
        repeater.dhis2_config = Dhis2Config.wrap(form.cleaned_data)
        repeater.save()
        org_unit_value_source = dict(repeater.dhis2_config.form_configs[0].org_unit_id)
        self.assertDictEqual(org_unit_value_source, {
            'doc_type': 'ConstantString',
            'value': 'dhis2_location_id',
            'commcare_data_type': None,
            'external_data_type': None,
            'direction': None,
        })
