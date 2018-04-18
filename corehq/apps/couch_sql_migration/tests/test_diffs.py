from __future__ import absolute_import
from __future__ import unicode_literals
from copy import deepcopy

from django.test import SimpleTestCase

from corehq.apps.couch_sql_migration.diff import (
    filter_form_diffs, FORM_IGNORED_DIFFS, PARTIAL_DIFFS,
    filter_case_diffs, CASE_IGNORED_DIFFS, filter_ledger_diffs
)
from corehq.apps.tzmigration.timezonemigration import FormJsonDiff, json_diff
from corehq.util.test_utils import softer_assert

DATE_DIFFS = [
    FormJsonDiff(
        diff_type='diff', path=('@date_modified',),
        old_value='2016-04-01T15:39:42Z', new_value='2016-04-01T15:39:42.000000Z'
    ),
    FormJsonDiff(
        diff_type='diff', path=('form', 'date_question'),
        old_value='2014-07-07T15:59:00.000000Z', new_value="2014-07-07T10:29:00.000000Z"
    ),
]

DELETION_DIFFS = [
    FormJsonDiff(diff_type='missing', path=('-deletion_id',), old_value='abc', new_value=Ellipsis),
    FormJsonDiff(diff_type='missing', path=('deletion_id',), old_value=Ellipsis, new_value='abc'),
    FormJsonDiff(diff_type='missing', path=('-deletion_date',), old_value='123', new_value=Ellipsis),
    FormJsonDiff(diff_type='missing', path=('deleted_on',), old_value=Ellipsis, new_value='123'),
]

REAL_DIFFS = [
    FormJsonDiff(diff_type='diff', path=('name',), old_value='Form1', new_value='Form2'),
    FormJsonDiff(diff_type='missing', path=('random_field',), old_value='legacy value', new_value=Ellipsis),
    FormJsonDiff(diff_type='type', path=('timeStart',), old_value='2016-04-01T15:39:42Z', new_value='not a date'),
]


def _get_partial_diffs(doc_type):
    diff_defaults = FormJsonDiff(diff_type='type', path=None, old_value=0, new_value=1)._asdict()
    return [
        FormJsonDiff(**dict(diff_defaults, **partial))
        for partial in PARTIAL_DIFFS[doc_type]
    ]


class DiffTestCases(SimpleTestCase):
    def setUp(self):
        super(DiffTestCases, self).setUp()
        self.softer_assert_context = softer_assert().__enter__()

    def tearDown(self):
        self.softer_assert_context.__exit__(None, None, None)
        super(DiffTestCases, self).tearDown()

    def _test_form_diff_filter(self, couch_form, sql_form, diffs, expected):
        filtered = filter_form_diffs(couch_form, sql_form, diffs)
        self.assertEqual(filtered, expected)

    def test_filter_form_diffs(self):
        partial_diffs = _get_partial_diffs('XFormInstance')

        self._test_form_diff_filter(
            {'doc_type': 'XFormInstance'}, {'doc_type': 'XFormInstance'},
            list(FORM_IGNORED_DIFFS) + partial_diffs + DATE_DIFFS + REAL_DIFFS,
            REAL_DIFFS
        )

    def test_filter_form_rename_fields_good(self):
        couch_form = {
            'doc_type': 'XFormDeprecated',
            'deprecated_date': 'abc',
        }
        sql_form = {
            'doc_type': 'XFormDeprecated',
            'edited_on': 'abc',
        }
        diffs = json_diff(couch_form, sql_form, track_list_indices=False)
        self._test_form_diff_filter(
            couch_form, sql_form,
            diffs + REAL_DIFFS,
            REAL_DIFFS
        )

    def test_filter_form_rename_fields_bad(self):
        couch_form = {
            'doc_type': 'XFormDeprecated',
            'deprecated_date': 'abc',
        }
        sql_form = {
            'doc_type': 'XFormDeprecated',
            'edited_on': '123',
        }
        diffs = json_diff(couch_form, sql_form, track_list_indices=False)
        self._test_form_diff_filter(
            couch_form, sql_form,
            diffs,
            [FormJsonDiff(
                diff_type='complex', path=('deprecated_date', 'edited_on'),
                old_value='abc', new_value='123'
            )]
        )

    def test_filter_form_deletion_fields(self):
        self._test_form_diff_filter(
            {'doc_type': 'XFormInstance-Deleted'}, {'doc_type': 'XFormInstance-Deleted'},
            DELETION_DIFFS + REAL_DIFFS,
            REAL_DIFFS
        )

    def test_filter_case_deletion_fields(self):
        couch_case = {'doc_type': 'CommCareCase-Deleted'}
        filtered = filter_case_diffs(couch_case, {}, DELETION_DIFFS + REAL_DIFFS)
        self.assertEqual(filtered, REAL_DIFFS)

    def test_filter_case_diffs(self):
        couch_case = {'doc_type': 'CommCareCase'}
        partial_diffs = _get_partial_diffs('CommCareCase')
        diffs = list(CASE_IGNORED_DIFFS) + partial_diffs + DATE_DIFFS + REAL_DIFFS
        filtered = filter_case_diffs(couch_case, {}, diffs)
        self.assertEqual(filtered, REAL_DIFFS)

    def test_filter_case_xform_id_diffs_good(self):
        couch_case = {
            'doc_type': 'CommCareCase',
            'xform_ids': ['123', '456']
        }
        sql_case = {
            'doc_type': 'CommCareCase',
            'xform_ids': ['456', '123']
        }

        diffs = json_diff(couch_case, sql_case, track_list_indices=False)
        self.assertEqual(2, len(diffs))
        filtered = filter_case_diffs(couch_case, sql_case, diffs + REAL_DIFFS)
        self.assertEqual(set(filtered), set([
            FormJsonDiff(diff_type='list_order', path=('xform_ids', '[*]'), old_value=None, new_value=None)
        ] + REAL_DIFFS))

    def test_filter_case_xform_id_diffs_bad(self):
        couch_case = {
            'doc_type': 'CommCareCase',
            'xform_ids': ['123', '456']
        }
        sql_case = {
            'doc_type': 'CommCareCase',
            'xform_ids': ['123', 'abc']
        }

        diffs = json_diff(couch_case, sql_case, track_list_indices=False)
        self.assertEqual(1, len(diffs))
        diffs = [
            FormJsonDiff(diff_type='diff', path=('xform_ids', '[*]'), old_value='456', new_value='abc')
        ]

        expected_diffs = REAL_DIFFS + [
            FormJsonDiff(diff_type='set_mismatch', path=('xform_ids', '[*]'), old_value='456', new_value='abc')
        ]
        filtered = filter_case_diffs(couch_case, sql_case, diffs + REAL_DIFFS)
        self.assertEqual(filtered, expected_diffs)

    def test_filter_case_user_id(self):
        couch_case = {
            'doc_type': 'CommCareCase',
            'user_id': 'e7ad965c70802884a7a67add763939e8',
            '@user_id': 'e7ad965c70802884a7a67add763939e8',
            '@case_id': '5ac45838-da5b-49f5-b236-0675ff924e9f'
        }
        sql_case = {
            'doc_type': 'CommCareCase',
            'user_id': 'e7ad965c70802884a7a67add763939e8',
            'case_id': '5ac45838-da5b-49f5-b236-0675ff924e9f'
        }

        diffs = json_diff(couch_case, sql_case, track_list_indices=False)
        filtered = filter_case_diffs(couch_case, sql_case, diffs)
        self.assertEqual(filtered, [])

    def test_filter_usercase_diff(self):
        couch_case = {
            'doc_type': 'CommCareCase',
            'hq_user_id': '123',
            'external_id': '',
            'type': 'commcare-user'
        }

        sql_case = {
            'doc_type': 'CommCareCase',
            'external_id': '123',
            'type': 'commcare-user'
        }

        user_case_diffs = json_diff(couch_case, sql_case)
        self.assertEqual(2, len(user_case_diffs))
        filtered = filter_case_diffs(couch_case, sql_case, user_case_diffs + REAL_DIFFS)
        self.assertEqual(filtered, REAL_DIFFS)

    def test_filter_usercase_diff_bad(self):
        couch_case = {
            'doc_type': 'CommCareCase',
            'hq_user_id': '123',
            'type': 'commcare-user'
        }

        sql_case = {
            'doc_type': 'CommCareCase',
            'type': 'commcare-user'
        }

        user_case_diffs = json_diff(couch_case, sql_case)
        self.assertEqual(1, len(user_case_diffs))
        filtered = filter_case_diffs(couch_case, sql_case, user_case_diffs)
        self.assertEqual(filtered, [
            FormJsonDiff(
                diff_type='complex', path=('hq_user_id', 'external_id'),
                old_value='123', new_value=Ellipsis
            )
        ])

    def test_filter_ledger_diffs(self):
        partial_diffs = _get_partial_diffs('LedgerValue')
        filtered = filter_ledger_diffs(partial_diffs + REAL_DIFFS)
        self.assertEqual(filtered, REAL_DIFFS)

    def test_filter_combo_fields(self):
        couch_case = {
            'doc_type': 'CommCareCase',
            '@date_modified': '2015-03-23T14:36:53Z'
        }
        sql_case = {
            'doc_type': 'CommCareCase',
            'modified_on': '2015-03-23T14:36:53.073000Z'
        }
        rename_date_diffs = json_diff(couch_case, sql_case)
        self.assertEqual(2, len(rename_date_diffs))
        filtered = filter_case_diffs(couch_case, sql_case, rename_date_diffs)
        self.assertEqual(filtered, [])

    def test_case_indices_order(self):
        couch_case = {
            'doc_type': 'CommCareCase',
            'indices': [
                {
                    "case_id": "fb698d47-4832-42b2-b28c-86d13adb45a2",
                    "identifier": "parent",
                    "referenced_id": "7ab03ccc-e5b7-4c8f-b88f-43ee3b0543a5",
                    "referenced_type": "Patient",
                    "relationship": "child"
                },
                {
                    "case_id": "fb698d47-4832-42b2-b28c-86d13adb45a2",
                    "identifier": "goal",
                    "referenced_id": "c2e938d9-7406-4fdf-87ab-67d92296705e",
                    "referenced_type": "careplan_goal",
                    "relationship": "child"
                }
            ]
        }

        sql_case = {
            'doc_type': 'CommCareCase',
            'indices': list(reversed(couch_case['indices']))
        }

        diffs = json_diff(couch_case, sql_case, track_list_indices=False)
        self.assertEqual(6, len(diffs))
        filtered_diffs = filter_case_diffs(couch_case, sql_case, diffs)
        self.assertEqual([], filtered_diffs)

    def test_multiple_case_indices_real_diff(self):
        couch_case = {
            'doc_type': 'CommCareCase',
            'indices': [
                {
                    "case_id": "fb698d47-4832-42b2-b28c-86d13adb45a2",
                    "identifier": "parent",
                    "referenced_id": "7ab03ccc-e5b7-4c8f-b88f-43ee3b0543a5",
                    "referenced_type": "Patient",
                    "relationship": "child"
                },
                {
                    "case_id": "fb698d47-4832-42b2-b28c-86d13adb45a2",
                    "identifier": "goal",
                    "referenced_id": "c2e938d9-7406-4fdf-87ab-67d92296705e",
                    "referenced_type": "careplan_goal",
                    "relationship": "child"
                }
            ]
        }

        sql_case = {
            'doc_type': 'CommCareCase',
            'indices': deepcopy(couch_case['indices'])
        }
        sql_case['indices'][0]['identifier'] = 'mother'

        expected_diffs = [
            FormJsonDiff(
                diff_type='diff', path=('indices', '[*]', 'identifier'),
                old_value='parent', new_value='mother')
        ]
        diffs = json_diff(couch_case, sql_case, track_list_indices=False)
        filtered_diffs = filter_case_diffs(couch_case, sql_case, diffs)
        self.assertEqual(expected_diffs, filtered_diffs)

    def test_single_case_indices_real_diff(self):
        couch_case = {
            'doc_type': 'CommCareCase',
            'indices': [
                {
                    "doc_type": "CommCareCaseIndex",
                    "case_id": "fb698d47-4832-42b2-b28c-86d13adb45a2",
                    "identifier": "parent",
                    "referenced_id": "7ab03ccc-e5b7-4c8f-b88f-43ee3b0543a5",
                    "referenced_type": "Patient",
                    "relationship": "child"
                }
            ]
        }

        sql_case = {
            'doc_type': 'CommCareCase',
            'indices': deepcopy(couch_case['indices'])
        }
        del sql_case['indices'][0]['doc_type']
        sql_case['indices'][0]['relationship'] = 'extension'

        expected_diffs = [
            FormJsonDiff(diff_type='diff', path=('indices', '[*]', 'relationship'), old_value='child', new_value='extension')
        ]
        diffs = json_diff(couch_case, sql_case, track_list_indices=False)
        filtered_diffs = filter_case_diffs(couch_case, sql_case, diffs)
        self.assertEqual(expected_diffs, filtered_diffs)
