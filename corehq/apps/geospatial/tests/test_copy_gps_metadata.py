import doctest

from django.test import SimpleTestCase

from corehq.apps.geospatial.management.commands.copy_gps_metadata import (
    get_form_cases,
)


class TestGetFormCases(SimpleTestCase):

    es_form = {
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

    def test_get_form_cases(self):
        cases = get_form_cases(self.es_form['form'])
        self.assertEqual(
            set(c['@case_id'] for c in cases),
            {
                '9f4aa71c-38d7-494d-8d41-4f2e01942f49',
                'c66ddcdc6a3547fdbfd6103292b55f92',
                '8ca34e7d441143c8bc9a9db44fa30c5e',
                'b4bdf708c25e49fe89933963b6552906',
            }
        )

    def test_get_form_cases_with_case_type(self):
        cases = get_form_cases(self.es_form['form'], 'person')
        self.assertEqual(
            set(c['@case_id'] for c in cases),
            {
                'c66ddcdc6a3547fdbfd6103292b55f92',
                '8ca34e7d441143c8bc9a9db44fa30c5e',
                'b4bdf708c25e49fe89933963b6552906',
            }
        )

    def test_get_no_form_cases(self):
        cases = get_form_cases(self.es_form['form'], 'not-a-case-type')
        self.assertEqual(
            set(c['@case_id'] for c in cases),
            set()
        )


def test_doctests():
    import corehq.apps.geospatial.management.commands.copy_gps_metadata as module

    results = doctest.testmod(module)
    assert results.failed == 0
