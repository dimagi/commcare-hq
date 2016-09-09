from django.test import SimpleTestCase

from corehq.apps.couch_sql_migration.diff import (
    filter_form_diffs, FORM_IGNORED_DIFFS, PARTIAL_DIFFS, DATE_FIELDS,
    filter_case_diffs, CASE_IGNORED_DIFFS, filter_ledger_diffs
)
from corehq.apps.tzmigration.timezonemigration import FormJsonDiff

DATE_DIFFS = [
    FormJsonDiff(
        diff_type='diff', path=('prefix', path,),
        old_value='2016-04-01T15:39:42Z', new_value='2016-04-01T15:39:42.000000Z'
    )
    for path in DATE_FIELDS
]

DELETION_DIFFS = [
    FormJsonDiff(diff_type='missing', path=('-deletion_id',), old_value='abc', new_value=Ellipsis),
    FormJsonDiff(diff_type='missing', path=('deletion_id',), old_value=Ellipsis, new_value='abc'),
    FormJsonDiff(diff_type='missing', path=('-deletion_date',), old_value='123', new_value=Ellipsis),
    FormJsonDiff(diff_type='missing', path=('deleted_on',), old_value=Ellipsis, new_value='123'),
]

REAL_DIFFS = [
    FormJsonDiff(diff_type='type', path=('@xmlns',), old_value='http://xmlns1', new_value='http://xmlns1'),
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
    def _test_form_diff_filter(self, doc_type, diffs, expected):
        filtered = filter_form_diffs(doc_type, diffs)
        self.assertEqual(filtered, expected)

    def test_filter_form_diffs(self):
        partial_diffs = _get_partial_diffs('XFormInstance')

        self._test_form_diff_filter(
            'XFormInstance',
            list(FORM_IGNORED_DIFFS) + partial_diffs + DATE_DIFFS + REAL_DIFFS,
            REAL_DIFFS
        )

    def test_filter_form_rename_fields(self):
        good_rename_diffs = [
            FormJsonDiff(diff_type='missing', path=('deprecated_date',), old_value='abc', new_value=Ellipsis),
            FormJsonDiff(diff_type='missing', path=('edited_on',), old_value=Ellipsis, new_value='abc'),
        ]
        bad_rename_diffs = [
            FormJsonDiff(diff_type='missing', path=('deprecated_date',), old_value='abc', new_value=Ellipsis),
            FormJsonDiff(diff_type='missing', path=('edited_on',), old_value=Ellipsis, new_value='123'),
        ]
        self._test_form_diff_filter(
            'XFormDeprecated',
            good_rename_diffs + bad_rename_diffs + REAL_DIFFS,
            bad_rename_diffs + REAL_DIFFS
        )

    def test_filter_form_deletion_fields(self):
        self._test_form_diff_filter(
            'XFormInstance-Deleted',
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

        diffs = [
            FormJsonDiff(diff_type=u'diff', path=('xform_ids', '[*]'), old_value=u'123', new_value=u'456'),
            FormJsonDiff(diff_type=u'diff', path=('xform_ids', '[*]'), old_value=u'455', new_value=u'123')
        ]

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

        diffs = [
            FormJsonDiff(diff_type=u'diff', path=('xform_ids', '[*]'), old_value=u'456', new_value=u'abc')
        ]

        filtered = filter_case_diffs(couch_case, sql_case, diffs + REAL_DIFFS)
        self.assertEqual(filtered, diffs + REAL_DIFFS)

    def test_filter_usercase_diff(self):
        couch_case = {
            'doc_type': 'CommCareCase',
            'hq_user_id': '123',
            'external_id': '',
            'type': 'commcare-user'
        }

        user_case_diffs = [
            FormJsonDiff(diff_type=u'diff', path=(u'external_id',), old_value=u'', new_value=u'123')
        ]
        filtered = filter_case_diffs(couch_case, {}, user_case_diffs + REAL_DIFFS)
        self.assertEqual(filtered, REAL_DIFFS)

    def test_filter_ledger_diffs(self):
        partial_diffs = _get_partial_diffs('LedgerValue')
        filtered = filter_ledger_diffs(partial_diffs + REAL_DIFFS)
        self.assertEqual(filtered, REAL_DIFFS)
