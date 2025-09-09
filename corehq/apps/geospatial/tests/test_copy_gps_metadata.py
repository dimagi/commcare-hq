import doctest
from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.geospatial.management.commands.copy_gps_metadata import (
    get_form_cases,
    iter_forms_with_location,
)


class TestGetFormCases(SimpleTestCase):
    def test_get_form_cases(self):
        cases = get_form_cases(FORM_JSON_1)
        self.assertEqual(
            set(c['@case_id'] for c in cases),
            {
                '9f4aa71c-38d7-494d-8d41-4f2e01942f49',
                'c66ddcdc6a3547fdbfd6103292b55f92',
                '8ca34e7d441143c8bc9a9db44fa30c5e',
                'b4bdf708c25e49fe89933963b6552906',
            },
        )

    def test_get_form_cases_with_case_type(self):
        cases = get_form_cases(FORM_JSON_1, 'person')
        self.assertEqual(
            set(c['@case_id'] for c in cases),
            {
                'c66ddcdc6a3547fdbfd6103292b55f92',
                '8ca34e7d441143c8bc9a9db44fa30c5e',
                'b4bdf708c25e49fe89933963b6552906',
            },
        )

    def test_get_parent_case_type(self):
        cases = get_form_cases(FORM_JSON_2, 'parent')
        self.assertEqual(
            set(c['@case_id'] for c in cases),
            {'2b6a17fb-1a08-49c2-bda7-5f5ae2daf47c'},
        )

    def test_get_child_case_type(self):
        cases = get_form_cases(FORM_JSON_2, 'child')
        self.assertEqual(
            set(c['@case_id'] for c in cases),
            {
                'b23cd4f8-316a-4472-b951-3e16d2380065',
                '5cb06ece-a36e-44df-b6d7-92b0ebf22ca0',
                'b1b88460-726b-466a-97d7-1ab97894e240',
            },
        )

    def test_get_form_cases_with_other_case_type(self):
        cases = get_form_cases(FORM_JSON_1, 'not-a-case-type')
        self.assertEqual(set(c['@case_id'] for c in cases), set())

    def test_form_with_no_cases(self):
        empty_es_form = {
            'doc_type': 'XFormInstance',
            'form': {
                '@version': '1',
                '@uiVersion': '1',
                '@xmlns': 'http://commcarehq.org/case',
                'meta': {},
                'case': [],
                '#type': 'system',
            },
        }
        cases = get_form_cases(empty_es_form['form'])
        self.assertEqual(len(cases), 0)


class TestIterFormsWithLocation(SimpleTestCase):
    @patch('corehq.apps.es.forms.FormES.scroll_ids_to_disk_and_iter_docs')
    def test_location_in_metadata_yields_form(self, mock_scroll):
        mock_scroll.return_value = (f for f in [
            {'form': {'meta': {'location': '55.948 -3.199'}, '@id': 'form1'}},
        ])
        forms = list(iter_forms_with_location('test-domain'))
        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0]['@id'], 'form1')

    @patch('corehq.apps.es.forms.FormES.scroll_ids_to_disk_and_iter_docs')
    def test_no_location_in_metadata_skips_form(self, mock_scroll):
        mock_scroll.return_value = (f for f in [
            {'form': {'meta': {}, '@id': 'form1'}},
        ])
        forms = list(iter_forms_with_location('test-domain'))
        self.assertEqual(len(forms), 0)

    @patch('corehq.apps.es.forms.FormES.scroll_ids_to_disk_and_iter_docs')
    def test_multiple_forms_returned(self, mock_scroll):
        mock_scroll.return_value = (f for f in [
            {'form': {'meta': {'location': '55.948 -3.199'}, '@id': 'form1'}},
            {'form': {'meta': {'location': '55.948 -3.199'}, '@id': 'form2'}},
        ])
        forms = list(iter_forms_with_location('test-domain'))
        self.assertEqual(len(forms), 2)
        self.assertEqual(forms[0]['@id'], 'form1')
        self.assertEqual(forms[1]['@id'], 'form2')


def test_doctests():
    import corehq.apps.geospatial.management.commands.copy_gps_metadata as module

    results = doctest.testmod(module)
    assert results.failed == 0


FORM_JSON_1 = {
    'doc_type': 'XFormInstance',
    'form': {
        '@version': '1',
        '@uiVersion': '1',
        '@xmlns': 'http://commcarehq.org/case',
        'meta': {
            '@xmlns': 'http://openrosa.org/jr/xforms',
            'deviceID': 'corehq.apps.case_importer.do_import.do_import',
            'timeStart': '2024-07-15T22:08:24.439433Z',
            'timeEnd': '2024-07-15T22:08:24.439433Z',
            'username': 'admin@example.com',
            'userID': '30ea99a67ab9d4bedcecbc943b0001c1',
            'instanceID': 'd4ec54dc9c48496e8b10ffbed3d4962a',
            'appVersion': None,
            'commcare_version': None,
            'app_build_version': None,
            'location': '55.94886 -3.19910 110 50',
            'geo_point': None,
        },
        'case': [
            {
                '@case_id': '9f4aa71c-38d7-494d-8d41-4f2e01942f49',
                '@date_modified': '2024-07-15T22:08:24.426330Z',
                '@xmlns': 'http://commcarehq.org/case/transaction/v2',
                'update': {'case_name': 'Testy McTestface'},
            },
            {
                '@case_id': 'c66ddcdc6a3547fdbfd6103292b55f92',
                '@date_modified': '2024-07-15T22:08:24.431091Z',
                '@user_id': '30ea99a67ab9d4bedcecbc943b0001c1',
                '@xmlns': 'http://commcarehq.org/case/transaction/v2',
                'create': {
                    'case_type': 'person',
                    'case_name': 'Alice',
                    'owner_id': '30ea99a67ab9d4bedcecbc943b0001c1',
                },
            },
            {
                '@case_id': '8ca34e7d441143c8bc9a9db44fa30c5e',
                '@date_modified': '2024-07-15T22:08:24.434748Z',
                '@user_id': '30ea99a67ab9d4bedcecbc943b0001c1',
                '@xmlns': 'http://commcarehq.org/case/transaction/v2',
                'create': {
                    'case_type': 'person',
                    'case_name': 'Bob',
                    'owner_id': '30ea99a67ab9d4bedcecbc943b0001c1',
                },
            },
            {
                '@case_id': 'b4bdf708c25e49fe89933963b6552906',
                '@date_modified': '2024-07-15T22:08:24.438592Z',
                '@user_id': '30ea99a67ab9d4bedcecbc943b0001c1',
                '@xmlns': 'http://commcarehq.org/case/transaction/v2',
                'create': {
                    'case_type': 'person',
                    'case_name': 'Charlie',
                    'owner_id': '30ea99a67ab9d4bedcecbc943b0001c1',
                },
            },
        ],
        '#type': 'system',
    },
    'auth_context': {'doc_type': 'DefaultAuthContext'},
    'openrosa_headers': {},
    'domain': 'demo',
    'app_id': None,
    'xmlns': 'http://commcarehq.org/case',
    'user_id': '30ea99a67ab9d4bedcecbc943b0001c1',
    'orig_id': None,
    'deprecated_form_id': None,
    'server_modified_on': '2024-07-15T22:08:24.569912Z',
    'received_on': '2024-07-15T22:08:24.445617Z',
    'edited_on': None,
    'partial_submission': False,
    'submit_ip': None,
    'last_sync_token': None,
    'problem': None,
    'date_header': None,
    'build_id': None,
    'state': 1,
    'initial_processing_complete': True,
    'external_blobs': {
        'form.xml': {
            'id': '936c89a4b85e476292109cf3818867a4',
            'content_type': 'text/xml',
            'content_length': 1830,
        }
    },
    'history': [],
    'backend_id': 'sql',
    'user_type': 'web',
    'inserted_at': '2024-07-16T10:14:27.678548Z',
    '__retrieved_case_ids': [
        '8ca34e7d441143c8bc9a9db44fa30c5e',
        'c66ddcdc6a3547fdbfd6103292b55f92',
        '9f4aa71c-38d7-494d-8d41-4f2e01942f49',
        'b4bdf708c25e49fe89933963b6552906',
    ],
    'doc_id': 'd4ec54dc9c48496e8b10ffbed3d4962a',
    '_id': 'd4ec54dc9c48496e8b10ffbed3d4962a',
}

FORM_JSON_2 = {
    '@uiVersion': '1',
    '@version': '6',
    '@name': 'Register Parent',
    '@xmlns': 'http://openrosa.org/formdesigner/76303AA3-9BD3-4DBE-A4FF-182E554B0168',
    'name': 'Bonnie',
    'num_children': '3',
    'children': [
        {
            'case': {
                '@case_id': 'b23cd4f8-316a-4472-b951-3e16d2380065',
                '@date_modified': '2024-07-17T17:09:43.359+01',
                '@user_id': '3c6d579a8abdddd07c033d1725b10735',
                '@xmlns': 'http://commcarehq.org/case/transaction/v2',
                'create': {
                    'case_name': 'Bonnie-Adeline',
                    'owner_id': '3c6d579a8abdddd07c033d1725b10735',
                    'case_type': 'child',
                },
                'update': '',
                'index': {
                    'parent': {
                        '@case_type': 'parent',
                        '#text': '2b6a17fb-1a08-49c2-bda7-5f5ae2daf47c',
                    }
                },
            },
            'name': 'Bonnie-Adeline',
        },
        {
            'case': {
                '@case_id': '5cb06ece-a36e-44df-b6d7-92b0ebf22ca0',
                '@date_modified': '2024-07-17T17:09:43.359+01',
                '@user_id': '3c6d579a8abdddd07c033d1725b10735',
                '@xmlns': 'http://commcarehq.org/case/transaction/v2',
                'create': {
                    'case_name': 'Bonnie-Bree',
                    'owner_id': '3c6d579a8abdddd07c033d1725b10735',
                    'case_type': 'child',
                },
                'update': '',
                'index': {
                    'parent': {
                        '@case_type': 'parent',
                        '#text': '2b6a17fb-1a08-49c2-bda7-5f5ae2daf47c',
                    }
                },
            },
            'name': 'Bonnie-Bree',
        },
        {
            'case': {
                '@case_id': 'b1b88460-726b-466a-97d7-1ab97894e240',
                '@date_modified': '2024-07-17T17:09:43.359+01',
                '@user_id': '3c6d579a8abdddd07c033d1725b10735',
                '@xmlns': 'http://commcarehq.org/case/transaction/v2',
                'create': {
                    'case_name': 'Bonnie-Celeste',
                    'owner_id': '3c6d579a8abdddd07c033d1725b10735',
                    'case_type': 'child',
                },
                'update': '',
                'index': {
                    'parent': {
                        '@case_type': 'parent',
                        '#text': '2b6a17fb-1a08-49c2-bda7-5f5ae2daf47c',
                    }
                },
            },
            'name': 'Bonnie-Celeste',
        },
    ],
    'case': {
        '@case_id': '2b6a17fb-1a08-49c2-bda7-5f5ae2daf47c',
        '@date_modified': '2024-07-17T17:09:43.359+01',
        '@user_id': '3c6d579a8abdddd07c033d1725b10735',
        '@xmlns': 'http://commcarehq.org/case/transaction/v2',
        'create': {
            'case_name': 'Bonnie',
            'owner_id': '3c6d579a8abdddd07c033d1725b10735',
            'case_type': 'parent',
        },
    },
    'meta': {
        '@xmlns': 'http://openrosa.org/jr/xforms',
        'deviceID': 'commcare_a6f44c75-d2de-4b07-9e6a-9fa303039ead',
        'timeStart': '2024-07-17T17:05:10.898+01',
        'timeEnd': '2024-07-17T17:09:43.359+01',
        'username': 'test',
        'userID': '3c6d579a8abdddd07c033d1725b10735',
        'instanceID': '917db979-8399-4b31-8394-491f817d9ec8',
        'appVersion': {
            '@xmlns': 'http://commcarehq.org/xforms',
            '#text': 'CommCare Android, version "2.53.1"(464694). App v6. '
            'CommCare Version 2.53.1. Build 464694, built on: 2023-07-31',
        },
        'drift': '0',
        'location': {
            '@xmlns': 'http://commcarehq.org/xforms',
            '#text': '55.94886 -3.19910 110 50',
        },
    },
    '#type': 'data',
}
