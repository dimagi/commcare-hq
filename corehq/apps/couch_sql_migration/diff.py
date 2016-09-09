from corehq.apps.tzmigration.timezonemigration import is_datetime

BASE_IGNORED_FORM_PATHS = {
    '_rev',
    'migrating_blobs_from_couch',
    '#export_tag',
    'computed_',
    'state',
    'computed_modified_on_',
    'deprecated_form_id',
    'path',
    'user_id',
    'external_blobs',
}

FORM_IGNORE_PATHS = {
    'XFormInstance': BASE_IGNORED_FORM_PATHS | {'problem', 'orig_id', 'edited_on'},
    'XFormInstance-Deleted': BASE_IGNORED_FORM_PATHS | {'problem', 'orig_id', 'edited_on'},
    'HQSubmission': BASE_IGNORED_FORM_PATHS | {'problem', 'orig_id', 'edited_on'},
    'XFormArchived': BASE_IGNORED_FORM_PATHS | {'edited_on'},
    'XFormError': BASE_IGNORED_FORM_PATHS | {'edited_on'},
    'XFormDuplicate': BASE_IGNORED_FORM_PATHS | {'edited_on'},
    'XFormDeprecated': BASE_IGNORED_FORM_PATHS,
}

FORM_PARTIAL_DIFFS = (
    {'diff_type': 'type', 'path': ('openrosa_headers', 'HTTP_X_OPENROSA_VERSION')},
)


def _form_ignored_diffs():
    from corehq.apps.tzmigration.timezonemigration import FormJsonDiff
    return (
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

FORM_IGNORED_DIFFS = _form_ignored_diffs()

CASE_IGNORED_PATHS = {
    ('_rev',),
    ('initial_processing_complete',),
    ('actions', '[*]'),
    ('id',),
    ('#export_tag',),
    ('computed_',),
    ('version',),
    ('case_attachments',),
    ('deleted',),
    ('export_tag',),
    ('computed_modified_on_',),
    ('case_id',),
    ('case_json',),
    ('modified_by',),
    ('indices', '[*]', 'case_id'),
}


CASE_PARTIAL_DIFFS = (
    {'diff_type': 'diff', 'path': ('owner_id',), 'old_value': ''},
    {'diff_type': 'diff', 'path': ('owner_id',), 'old_value': None},
)


def _case_ignored_diffs():
    from corehq.apps.tzmigration.timezonemigration import FormJsonDiff
    return (
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
    )

CASE_IGNORED_DIFFS = _case_ignored_diffs()


LEDGER_IGNORED_PATHS = {
    ('_id',),
}


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
    paths_to_ignore = FORM_IGNORE_PATHS[doc_type]
    filtered = [
        diff for diff in diffs
        if diff.path[0] not in paths_to_ignore and diff not in FORM_IGNORED_DIFFS
    ]
    filtered = _filter_renamed_fields(filtered, doc_type)
    filtered = _filter_partial_diffs(filtered, FORM_PARTIAL_DIFFS)
    filtered = _filter_date_diffs(filtered)
    return filtered


def _filter_partial_diffs(diffs, partial_diffs_to_exclude):
    """Filter out diffs that match a subset of attributes
    :type partial_diffs_to_exclude: dict([(attr, value)...])
    """
    def _partial_match(diff):
        print diff
        for partial in partial_diffs_to_exclude:
            print partial
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


def filter_case_diffs(doc_type, diffs):
    filtered_diffs = [
        diff for diff in diffs
        if diff.path not in CASE_IGNORED_PATHS and diff not in CASE_IGNORED_DIFFS
    ]
    filtered_diffs = _filter_renamed_fields(filtered_diffs, doc_type)
    filtered_diffs = _filter_partial_diffs(filtered_diffs, CASE_PARTIAL_DIFFS)
    filtered_diffs = _filter_date_diffs(filtered_diffs)
    return filtered_diffs


def filter_ledger_diffs(diffs):
    return [
        diff for diff in diffs
        if diff.path not in LEDGER_IGNORED_PATHS
    ]


def _filter_date_diffs(diffs):
    def _both_dates(old, new):
        return is_datetime(old) and is_datetime(new)

    def _date_diff(diff):
        return diff.diff_type == 'diff' and diff.path[-1] in DATE_FIELDS

    return [
        diff for diff in diffs
        if not _date_diff(diff) or not _both_dates(diff.old_value, diff.new_value)
    ]
