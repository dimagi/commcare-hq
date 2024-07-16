import doctest

from django.test import SimpleTestCase

from corehq.apps.geospatial.management.commands.copy_gps_metadata import (
    get_form_cases,
)


class TestGetFormCases(SimpleTestCase):

    form = {
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
            'appVersion': {'@xmlns': 'http://commcarehq.org/xforms'},
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
    }

    def test_get_form_cases(self):
        cases = get_form_cases(self.form)
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
        cases = get_form_cases(self.form, 'person')
        self.assertEqual(
            set(c['@case_id'] for c in cases),
            {
                'c66ddcdc6a3547fdbfd6103292b55f92',
                '8ca34e7d441143c8bc9a9db44fa30c5e',
                'b4bdf708c25e49fe89933963b6552906',
            }
        )

    def test_get_no_form_cases(self):
        cases = get_form_cases(self.form, 'not-a-case-type')
        self.assertEqual(
            set(c['@case_id'] for c in cases),
            set()
        )


def test_doctests():
    import corehq.apps.geospatial.management.commands.copy_gps_metadata as module

    results = doctest.testmod(module)
    assert results.failed == 0
