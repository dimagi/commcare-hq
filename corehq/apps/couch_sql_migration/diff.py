from corehq.apps.tzmigration.timezonemigration import is_datetime, FormJsonDiff

PARTIAL_DIFFS = {
    'XFormInstance*': [
        {'path': ('_rev',)},
        {'path': ('migrating_blobs_from_couch',)},
        {'path': ('#export_tag',)},
        {'path': ('computed_',)},
        {'path': ('state',)},
        {'path': ('computed_modified_on_',)},
        {'path': ('deprecated_form_id',)},
        {'path': ('path',)},
        {'path': ('user_id',)},
        {'path': ('external_blobs',)},
        {'diff_type': 'type', 'path': ('openrosa_headers', 'HTTP_X_OPENROSA_VERSION')},
    ],
    'XFormInstance': [
        {'path': ('problem',)},
        {'path': ('orig_id',)},
        {'path': ('edited_on',)},
    ],
    'XFormInstance-Deleted': [
        {'path': ('problem',)},
        {'path': ('orig_id',)},
        {'path': ('edited_on',)},
    ],
    'HQSubmission': [
        {'path': ('problem',)},
        {'path': ('orig_id',)},
        {'path': ('edited_on',)},
    ],
    'XFormArchived': [
        {'path': ('edited_on',)},
    ],
    'XFormError': [
        {'path': ('edited_on',)},
    ],
    'XFormDuplicate': [
        {'path': ('edited_on',)},
    ],
    'XFormDeprecated': [],
    'CommCareCase': [
        {'path': ('_rev',)},
        {'path': ('initial_processing_complete',)},
        {'path': ('actions', '[*]')},
        {'path': ('id',)},
        {'path': ('#export_tag',)},
        {'path': ('computed_',)},
        {'path': ('version',)},
        {'path': ('case_attachments',)},
        {'path': ('deleted',)},
        {'path': ('export_tag',)},
        {'path': ('computed_modified_on_',)},
        {'path': ('case_id',)},
        {'path': ('case_json',)},
        {'path': ('modified_by',)},
        {'path': ('indices', '[*]', 'case_id')},
        {'diff_type': 'diff', 'path': ('owner_id',), 'old_value': ''},
        {'diff_type': 'diff', 'path': ('owner_id',), 'old_value': None},
    ],
    'LedgerValue': [
        {'path': ('_id',)},
    ]
}


FORM_IGNORED_DIFFS = (
    FormJsonDiff(
        diff_type=u'missing', path=(u'history', u'[*]', u'doc_type'),
        old_value=u'XFormOperation', new_value=Ellipsis
    ),
    FormJsonDiff(
        diff_type=u'diff', path=(u'doc_type',),
        old_value=u'HQSubmission', new_value=u'XFormInstance'
    ),
    FormJsonDiff(diff_type=u'missing', path=(u'deleted_on',), old_value=Ellipsis, new_value=None),
    FormJsonDiff(diff_type=u'missing', path=(u'location_',), old_value=[], new_value=Ellipsis),
)

CASE_IGNORED_DIFFS = (
    FormJsonDiff(diff_type=u'type', path=(u'name',), old_value=u'', new_value=None),
    FormJsonDiff(diff_type=u'type', path=(u'closed_by',), old_value=u'', new_value=None),
    FormJsonDiff(diff_type=u'missing', path=(u'location_id',), old_value=Ellipsis, new_value=None),
    FormJsonDiff(
        diff_type=u'missing', path=(u'indices', u'[*]', u'doc_type'),
        old_value=u'CommCareCaseIndex', new_value=Ellipsis),
    FormJsonDiff(diff_type=u'missing', path=(u'referrals',), old_value=[], new_value=Ellipsis),
    FormJsonDiff(diff_type=u'missing', path=(u'location_',), old_value=[], new_value=Ellipsis),
    FormJsonDiff(diff_type=u'type', path=(u'type',), old_value=None, new_value=u''),
    # this happens for cases where the creation form has been archived but the case still has other forms
    FormJsonDiff(diff_type=u'type', path=(u'owner_id',), old_value=None, new_value=u''),
    FormJsonDiff(diff_type=u'missing', path=(u'closed_by',), old_value=Ellipsis, new_value=None),
    FormJsonDiff(diff_type=u'type', path=(u'external_id',), old_value=u'', new_value=None),
    FormJsonDiff(diff_type=u'missing', path=(u'deleted_on',), old_value=Ellipsis, new_value=None),
)

DATE_FIELDS = {
    'modified_on',
    'server_modified_on',
    'opened_on',
    'closed_on',
    'timeStart',
    'timeEnd',
    '@date_modified',
}


RENAMED_FIELDS = {
    'XFormDeprecated': [('deprecated_date', 'edited_on')],
    'XFormInstance-Deleted': [('-deletion_id', 'deletion_id'), ('-deletion_date', 'deleted_on')],
    'CommCareCase-Deleted': [('-deletion_id', 'deletion_id'), ('-deletion_date', 'deleted_on')],
}


def filter_form_diffs(doc_type, diffs):
    filtered = _filter_exact_matches(diffs, FORM_IGNORED_DIFFS)
    partial_diffs = PARTIAL_DIFFS[doc_type] + PARTIAL_DIFFS['XFormInstance*']
    filtered = _filter_partial_matches(filtered, partial_diffs)
    filtered = _filter_renamed_fields(filtered, doc_type)
    filtered = _filter_date_diffs(filtered)
    return filtered


def filter_case_diffs(couch_case, diffs):
    doc_type = couch_case['doc_type']
    filtered_diffs = _filter_exact_matches(diffs, CASE_IGNORED_DIFFS)
    filtered_diffs = _filter_partial_matches(filtered_diffs, PARTIAL_DIFFS['CommCareCase'])
    filtered_diffs = _filter_renamed_fields(filtered_diffs, doc_type)
    filtered_diffs = _filter_date_diffs(filtered_diffs)
    filtered_diffs = _filter_user_case_diffs(couch_case, filtered_diffs)
    return filtered_diffs


def filter_ledger_diffs(diffs):
    return _filter_partial_matches(diffs, PARTIAL_DIFFS['LedgerValue'])


def _filter_exact_matches(diffs, diffs_to_ignore):
    return [
        diff for diff in diffs
        if diff not in diffs_to_ignore
    ]


def _filter_partial_matches(diffs, partial_diffs_to_exclude):
    """Filter out diffs that match a subset of attributes
    :type partial_diffs_to_exclude: dict([(attr, value)...])
    """
    def _partial_match(diff):
        for partial in partial_diffs_to_exclude:
            if all(getattr(diff, attr) == val for attr, val in partial.items()):
                return True
        return False

    return [
        diff for diff in diffs
        if not _partial_match(diff)
    ]


def _filter_renamed_fields(diffs, doc_type):
    if doc_type in RENAMED_FIELDS:
        renames = RENAMED_FIELDS[doc_type]
        for rename in renames:
            _check_renamed_fields(diffs, *rename)

    return diffs


def _check_renamed_fields(filtered_diffs, couch_field_name, sql_field_name):
    from corehq.apps.tzmigration.timezonemigration import FormJsonDiff
    sql_fields = [diff for diff in filtered_diffs if diff.path[0] == sql_field_name]
    couch_fields = [diff for diff in filtered_diffs if diff.path[0] == couch_field_name]
    if sql_fields and couch_fields:
        sql_field = sql_fields[0]
        couch_field = couch_fields[0]
        filtered_diffs.remove(sql_field)
        filtered_diffs.remove(couch_field)
        if couch_field.old_value != sql_field.new_value:
            filtered_diffs.append(FormJsonDiff(
                diff_type='complex', path=(couch_field_name, sql_field_name),
                old_value=couch_field.old_value, new_value=sql_field.new_value
            ))


def _filter_date_diffs(diffs):
    def _both_dates(old, new):
        return is_datetime(old) and is_datetime(new)

    def _date_diff(diff):
        return diff.diff_type == 'diff' and diff.path[-1] in DATE_FIELDS

    return [
        diff for diff in diffs
        if not _date_diff(diff) or not _both_dates(diff.old_value, diff.new_value)
    ]


def _filter_user_case_diffs(couch_case, diffs):
    if 'hq_user_id' not in couch_case:
        return diffs

    hq_user_id = couch_case['hq_user_id']
    external_id_diffs = [diff for diff in diffs if diff.diff_type == 'diff' and diff.path == (u'external_id',)]
    for diff in external_id_diffs:
        if diff.old_value in ('', Ellipsis, None) and diff.new_value == hq_user_id:
            diffs.remove(diff)

    return diffs
