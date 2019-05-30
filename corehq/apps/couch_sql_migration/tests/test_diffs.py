from __future__ import absolute_import
from __future__ import unicode_literals
from copy import deepcopy

from attr import fields_dict
from django.test import SimpleTestCase

from corehq.apps.couch_sql_migration.diff import (
    filter_case_diffs,
    filter_form_diffs,
    filter_ledger_diffs,
    load_ignore_rules,
)
from corehq.apps.tzmigration.timezonemigration import FormJsonDiff, json_diff, MISSING
from corehq.util.test_utils import softer_assert

from ..diffrule import ANY


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
    FormJsonDiff(diff_type='missing', path=('-deletion_id',), old_value='abc', new_value=MISSING),
    FormJsonDiff(diff_type='missing', path=('deletion_id',), old_value=MISSING, new_value='abc'),
    FormJsonDiff(diff_type='missing', path=('-deletion_date',), old_value='123', new_value=MISSING),
    FormJsonDiff(diff_type='missing', path=('deleted_on',), old_value=MISSING, new_value='123'),
]

TEXT_XMLNS_DIFFS = [
    FormJsonDiff(diff_type='missing', path=('path', 'to', '#text'), old_value='', new_value="text?"),
    FormJsonDiff(diff_type='missing', path=('path', 'to', '@xmlns'), old_value='', new_value="xml"),
    FormJsonDiff(diff_type='missing', path=('#text',), old_value=MISSING, new_value="text?"),
    FormJsonDiff(diff_type='missing', path=('@xmlns',), old_value=MISSING, new_value="xml"),
]

REAL_DIFFS = [
    FormJsonDiff(diff_type='diff', path=('name',), old_value='Form1', new_value='Form2'),
    FormJsonDiff(diff_type='missing', path=('random_field',), old_value='legacy value', new_value=MISSING),
    FormJsonDiff(diff_type='type', path=('timeStart',), old_value='2016-04-01T15:39:42Z', new_value='not a date'),
]


def _make_ignored_diffs(doc_type):
    diff_defaults = dict(diff_type='type', path=('data',), old_value=0, new_value=1)
    diffs = [
        FormJsonDiff(**_diff_args(rule, diff_defaults))
        for type in [doc_type, doc_type + "*"]
        for rule in load_ignore_rules().get(type, [])
        if not _has_check(rule)
    ]
    assert diffs, "expected diffs for %s" % doc_type
    return diffs


def _has_check(rule):
    return rule.check is not fields_dict(type(rule))["check"].default


def _diff_args(ignore_rule, diff_defaults):
    kwargs = {}
    for attr, key in [
        ("type", "diff_type"),
        ("path", "path"),
        ("old", "old_value"),
        ("new", "new_value"),
    ]:
        value = getattr(ignore_rule, attr)
        kwargs[key] = (value if value is not ANY else diff_defaults[key])
    return kwargs


@softer_assert()
class DiffTestCases(SimpleTestCase):

    maxDiff = None

    def _test_form_diff_filter(self, couch_form, sql_form, diffs=None, expected=REAL_DIFFS):
        if diffs is None:
            diffs = json_diff(couch_form, sql_form, track_list_indices=False)
            self.assertTrue(diffs)
            diffs += REAL_DIFFS
        filtered = filter_form_diffs(couch_form, sql_form, diffs)
        self.assertEqual(filtered, expected)

    def test_filter_form_diffs(self):
        ignored_diffs = _make_ignored_diffs('XFormInstance')
        self._test_form_diff_filter(
            {'doc_type': 'XFormInstance'},
            {'doc_type': 'XFormInstance'},
            ignored_diffs + DATE_DIFFS + REAL_DIFFS,
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
        assert len(diffs) == 2, diffs
        self._test_form_diff_filter(couch_form, sql_form, diffs + REAL_DIFFS)

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
        couch_doc = {
            'doc_type': 'XFormInstance-Deleted',
            '-deletion_id': 'abc',
            '-deletion_date': '123',
        }
        sql_doc = {
            'doc_type': 'XFormInstance-Deleted',
            'deletion_id': 'abc',
            'deleted_on': '123',
        }
        self._test_form_diff_filter(couch_doc, sql_doc, DELETION_DIFFS + REAL_DIFFS)

    def test_filter_text_xmlns_fields(self):
        self._test_form_diff_filter(
            {'doc_type': 'XFormInstance'},
            {'doc_type': 'XFormInstance'},
            TEXT_XMLNS_DIFFS + REAL_DIFFS,
        )

    def test_filter_case_deletion_fields(self):
        couch_case = {
            'doc_type': 'CommCareCase-Deleted',
            '-deletion_id': 'abc',
            '-deletion_date': '123',
        }
        sql_case = {
            'doc_type': 'CommCareCase-Deleted',
            'deletion_id': 'abc',
            'deleted_on': '123',
        }
        filtered = filter_case_diffs(couch_case, sql_case, DELETION_DIFFS + REAL_DIFFS)
        self.assertEqual(filtered, REAL_DIFFS)

    def test_filter_missing_case_deletion_id(self):
        couch_case = {
            'doc_type': 'CommCareCase-Deleted',
        }
        sql_case = {
            'doc_type': 'CommCareCase-Deleted',
            'deletion_id': None,
        }
        diffs = json_diff(couch_case, sql_case, track_list_indices=False)
        filtered = filter_case_diffs(couch_case, sql_case, diffs)
        self.assertEqual(filtered, [])

    def test_filter_case_deleted_on_in_sql(self):
        couch_case = {
            'doc_type': 'CommCareCase-Deleted',
        }
        sql_case = {
            'doc_type': 'CommCareCase-Deleted',
            'deleted_on': '123',
        }
        diffs = json_diff(couch_case, sql_case, track_list_indices=False)
        self.assertTrue(diffs)
        filtered = filter_case_diffs(couch_case, sql_case, diffs + REAL_DIFFS)
        self.assertEqual(filtered, REAL_DIFFS)

    def test_filter_case_diffs(self):
        couch_case = {'doc_type': 'CommCareCase'}
        diffs = _make_ignored_diffs('CommCareCase') + DATE_DIFFS + REAL_DIFFS
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
        self.assertEqual(filtered, REAL_DIFFS)

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

        expected_diffs = [
            FormJsonDiff(diff_type='set_mismatch', path=('xform_ids', '[*]'), old_value='456', new_value='abc')
        ] + REAL_DIFFS
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
                diff_type='missing', path=('hq_user_id',),
                old_value='123', new_value=MISSING
            )
        ])

    def test_filter_ledger_diffs(self):
        ignored_diffs = _make_ignored_diffs('LedgerValue')
        filtered = filter_ledger_diffs(ignored_diffs + REAL_DIFFS)
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

    def test_filter_modified_on(self):
        couch_case = {
            'doc_type': 'CommCareCase',
            'modified_on': '2015-03-23T14:36:53Z'
        }
        sql_case = {
            'doc_type': 'CommCareCase',
            'modified_on': '2015-03-23T14:36:53.073000Z'
        }
        date_diffs = json_diff(couch_case, sql_case)
        self.assertEqual(1, len(date_diffs))
        filtered = filter_case_diffs(couch_case, sql_case, date_diffs)
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

    def test_case_obsolete_location_field(self):
        couch_case = {
            'doc_type': 'CommCareCase',
            'location_': ['abc', 'def']
        }

        sql_case = {
            'doc_type': 'CommCareCase',
        }

        diffs = json_diff(couch_case, sql_case, track_list_indices=False)
        self.assertTrue(diffs)
        self.assertEqual(filter_case_diffs(couch_case, sql_case, diffs), [])

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
            FormJsonDiff(
                diff_type='diff',
                path=('indices', '[*]', 'relationship'),
                old_value='child',
                new_value='extension',
            )
        ]
        diffs = json_diff(couch_case, sql_case, track_list_indices=False)
        filtered_diffs = filter_case_diffs(couch_case, sql_case, diffs)
        self.assertEqual(expected_diffs, filtered_diffs)

    def test_case_attachments(self):
        couch_case = {
            'doc_type': 'CommCareCase',
            'case_attachments': {
                'xyz': {
                    'doc_type': 'ignored',
                    'attachment_properties': 'ignored',
                    'attachment_from': 'ignored',
                    'attachment_src': 'ignored',
                    'server_mime': 'ignored',
                    'attachment_name': 'ignored',
                    'server_md5': 'ignored',
                    'identifier': 'xyz',
                    'attachment_size': 123,
                    'unexpected': 'value',
                    'properties': 'value',
                },
            },
        }
        sql_case = {
            'doc_type': 'CommCareCase',
            'case_attachments': {
                'xyz': {
                    'name': 'xyz',
                    'content_length': 123,
                    'content_type': 'ignored-sql',
                    # for testing only, not an expected transformation
                    'properties': 'eulav',
                },
            },
        }

        diffs = json_diff(couch_case, sql_case, track_list_indices=False)
        filtered = filter_case_diffs(couch_case, sql_case, diffs)
        self.assertEqual(filtered, [
            FormJsonDiff('missing', ('case_attachments', 'xyz', 'unexpected'), 'value', MISSING),
            FormJsonDiff('diff', ('case_attachments', 'xyz', 'properties'), 'value', 'eulav'),
        ])

    def test_form_with_couch_attachments(self):
        couch_form = {
            "doc_type": "XFormInstance",
            "_attachments": {'form.xml': {}},
        }
        sql_form = {
            "doc_type": "XFormInstance",
        }
        self._test_form_diff_filter(couch_form, sql_form)

    def test_form_with_obsolete_location_fields(self):
        couch_doc = {
            "doc_type": "XFormInstance",
            "location_id": "deadbeef",
            "location_": ["deadbeef", "cafebabe"],
            "xmlns": "http://commtrack.org/supply_point",
        }
        sql_doc = {
            "doc_type": "XFormInstance",
            "xmlns": "http://commtrack.org/supply_point",
        }
        self._test_form_diff_filter(couch_doc, sql_doc)

    def test_form_with_opened_by_diff(self):
        couch_case = {
            "doc_type": "XFormInstance",
            "opened_by": "somebody",
            "actions": [
                {"action_type": "close"},
                {"action_type": "rebuild"},
            ],
        }
        sql_case = {
            "doc_type": "XFormInstance",
            "opened_by": "somebody else",
        }
        diffs = json_diff(couch_case, sql_case, track_list_indices=False)
        filtered = filter_case_diffs(couch_case, sql_case, diffs)
        self.assertEqual(filtered, [])
