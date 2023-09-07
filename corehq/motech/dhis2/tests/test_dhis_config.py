import json
from django.test.testcases import TestCase

from django.test import SimpleTestCase

from jsonobject.base_properties import BadValueError

from corehq.motech.dhis2.dhis2_config import Dhis2CaseConfig
from corehq.motech.dhis2.forms import Dhis2ConfigForm
from corehq.motech.dhis2.repeaters import Dhis2Repeater
from corehq.motech.models import ConnectionSettings


class TestDhisConfigValidation(TestCase):

    def setUp(self):
        self.domain = 'test-dhis2-domain'
        self.conn = ConnectionSettings.objects.create(url="http://fakeurl.com", domain=self.domain)

    def test_form_validation(self):
        config = {
            'form_configs': [{}]
        }
        form = Dhis2ConfigForm(data=config)
        self.assertFalse(form.is_valid())
        self.assertDictEqual(form.errors, {
            'form_configs': [
                'The "xmlns" property is required. Please specify the XMLNS of the form.',
                'The "program_id" property is required. Please specify the DHIS2 Program of the event.',
                'The "datavalue_maps" property is required. Please map CommCare values to DHIS2 data elements.',
            ]
        })

    def test_empty_json(self):
        config = {
            'form_configs': [{}]
        }
        repeater = Dhis2Repeater(
            connection_settings=self.conn,
            domain=self.domain
        )
        repeater.dhis2_config = config
        with self.assertRaises(BadValueError) as e:
            repeater.save()
        self.assertEqual(
            str(e.exception),
            "Property xmlns is required."
        )

    def test_missing_program_id(self):
        config = {
            'form_configs': [{
                'xmlns': 'test_xmlns',
            }]
        }
        repeater = Dhis2Repeater(connection_settings=self.conn, domain=self.domain)
        repeater.dhis2_config = config
        with self.assertRaises(BadValueError) as e:
            repeater.save()
        self.assertEqual(
            str(e.exception),
            'Property program_id is required.'
        )

    def test_minimal_config(self):
        config = {
            'form_configs': json.dumps([{
                'xmlns': 'test_xmlns',
                'program_id': 'test program',
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

        repeater = Dhis2Repeater(
            connection_settings=self.conn,
            domain=self.domain
        )
        repeater.dhis2_config = form.cleaned_data
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

        repeater = Dhis2Repeater(
            connection_settings=self.conn,
            domain=self.domain
        )
        repeater.dhis2_config = form.cleaned_data
        with self.assertRaises(BadValueError) as e:
            repeater.save()
        self.assertEqual(
            str(e.exception),
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

        repeater = Dhis2Repeater(
            connection_settings=self.conn,
            domain=self.domain
        )
        repeater.dhis2_config = form.cleaned_data
        repeater.save()

    def test_org_unit_id_migration(self):
        config = {
            'form_configs': json.dumps([{
                'xmlns': 'test_xmlns',
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

        repeater = Dhis2Repeater(
            connection_settings=self.conn,
            domain=self.domain
        )
        repeater.dhis2_config = form.cleaned_data
        repeater.save()
        org_unit_value_source = dict(repeater.dhis2_config['form_configs'][0]['org_unit_id'])
        self.assertDictEqual(org_unit_value_source, {'value': 'dhis2_location_id'})


class TestDhis2CaseConfig(SimpleTestCase):

    def test_default(self):
        conf = Dhis2CaseConfig.wrap({
            'case_type': 'foo',
            'te_type_id': 'abc12345678',
            'tei_id': {'case_property': 'external_id'},
            'org_unit_id': {'case_property': 'dhis2_org_unit_id'},
            'attributes': {},
            'form_configs': [],
            'finder_config': {},
            # relationships_to_export not specified
        })
        self.assertEqual(conf.relationships_to_export, [])

    def test_one_relationship_given(self):
        Dhis2CaseConfig.wrap({
            'case_type': 'foo',
            'te_type_id': 'abc12345678',
            'tei_id': {'case_property': 'external_id'},
            'org_unit_id': {'case_property': 'dhis2_org_unit_id'},
            'attributes': {},
            'form_configs': [],
            'finder_config': {},
            'relationships_to_export': [{
                'identifier': 'parent',
                'referenced_type': 'bar',
                'subcase_to_supercase_dhis2_id': 'abc12345678',
            }]
        })

    def test_index_given_twice(self):
        Dhis2CaseConfig.wrap({
            'case_type': 'foo',
            'te_type_id': 'abc12345678',
            'tei_id': {'case_property': 'external_id'},
            'org_unit_id': {'case_property': 'dhis2_org_unit_id'},
            'attributes': {},
            'form_configs': [],
            'finder_config': {},
            'relationships_to_export': [
                {
                    'identifier': 'parent',
                    'referenced_type': 'bar',
                    'subcase_to_supercase_dhis2_id': 'abc12345678',
                },
                {
                    'identifier': 'parent',
                    'referenced_type': 'bar',
                    'supercase_to_subcase_dhis2_id': 'def90123456',
                },
            ]
        })
