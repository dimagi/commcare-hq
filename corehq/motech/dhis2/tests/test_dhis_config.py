from __future__ import absolute_import
from __future__ import unicode_literals


from django.test import SimpleTestCase
from fakecouch import FakeCouchDb
from jsonobject.base_properties import BadValueError

from corehq.motech.dhis2.dhis2_config import Dhis2FormConfig
from corehq.motech.dhis2.forms import Dhis2ConfigForm
from corehq.motech.dhis2.repeaters import Dhis2Repeater

import json


class TestDhisConfigValidation(SimpleTestCase):

    def setUp(self):
        self.db = Dhis2Repeater.get_db()
        self.fakedb = FakeCouchDb()
        Dhis2Repeater.set_db(self.fakedb)

    def tearDown(self):
        Dhis2Repeater.set_db(self.db)

    def test_empty_json(self):
        config = {
            'form_configs': [{}]
        }
        form = Dhis2ConfigForm(data=config)
        self.assertTrue(form.is_valid())
        data = form.cleaned_data
        repeater = Dhis2Repeater()
        repeater.dhis2_config.form_configs = list(map(Dhis2FormConfig.wrap, data['form_configs']))
        with self.assertRaises(BadValueError) as e:
            repeater.save()
        self.assertEqual(
            e.exception.message,
            "Property program_id is required."
        )

    def test_missing_event_date(self):
        config = {
            'form_configs': json.dumps([{
                'program_id': 'test program'
            }])
        }
        form = Dhis2ConfigForm(data=config)
        self.assertTrue(form.is_valid())
        data = form.cleaned_data
        repeater = Dhis2Repeater()
        repeater.dhis2_config.form_configs = list(map(Dhis2FormConfig.wrap, data['form_configs']))
        with self.assertRaises(BadValueError) as e:
            repeater.save()
        self.assertEqual(
            e.exception.message,
            'Property event_date is required.'
        )

    def test_minimal_config(self):
        config = {
            'form_configs': json.dumps([{
                'program_id': 'test program',
                'event_date': {
                    'doc_type': 'FormQuestion',
                    'form_question': '/data/event_date'
                }
            }])
        }
        form = Dhis2ConfigForm(data=config)
        self.assertTrue(form.is_valid())
        data = form.cleaned_data
        repeater = Dhis2Repeater()
        repeater.dhis2_config.form_configs = list(map(Dhis2FormConfig.wrap, data['form_configs']))
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
                'org_unit_id': 'dhis2_location_id',
                'datavalue_maps': [
                    {}
                ]
            }])
        }
        form = Dhis2ConfigForm(data=config)
        self.assertTrue(form.is_valid())
        data = form.cleaned_data
        repeater = Dhis2Repeater()
        repeater.dhis2_config.form_configs = list(map(Dhis2FormConfig.wrap, data['form_configs']))
        with self.assertRaises(BadValueError) as e:
            repeater.save()
        self.assertEqual(
            e.exception.message,
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
                'org_unit_id': 'dhis2_location_id',
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
        data = form.cleaned_data
        repeater = Dhis2Repeater()
        repeater.dhis2_config.form_configs = list(map(Dhis2FormConfig.wrap, data['form_configs']))
        repeater.save()
