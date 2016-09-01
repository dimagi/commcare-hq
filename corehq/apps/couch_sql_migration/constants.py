BASE_IGNORED_FORM_PATHS = {
    '_rev',
    'migrating_blobs_from_couch',
    '#export_tag',
    'computed_',
    'state',
    'edited_on',
    'computed_modified_on_',
    'deprecated_form_id',
    'path',
    'user_id',
    'external_blobs',
}

FORM_IGNORE_PATHS = {
    'XFormInstance': BASE_IGNORED_FORM_PATHS | {'problem', 'orig_id'},
    'XFormArchived': BASE_IGNORED_FORM_PATHS | {'problem', 'orig_id'},
    'XFormError': BASE_IGNORED_FORM_PATHS,
    'XFormDuplicate': BASE_IGNORED_FORM_PATHS,
}


def _form_ignored_diffs():
    from corehq.apps.tzmigration.timezonemigration import FormJsonDiff
    return (
        FormJsonDiff(
            diff_type=u'missing', path=(u'history', u'[*]', u'doc_type'),
            old_value=u'XFormOperation', new_value=Ellipsis
        ),
    )

FORM_IGNORED_DIFFS = _form_ignored_diffs()

CASE_IGNORED_PATHS = {
    '_rev',
    'initial_processing_complete',
    'actions',
    'id',
    '#export_tag',
    'computed_',
    'version',
    'case_attachments',
    'deleted',
    'export_tag',
    'computed_modified_on_',
    'case_id',
    'case_json',
    'modified_by',
}


def _case_ignored_diffs():
    from corehq.apps.tzmigration.timezonemigration import FormJsonDiff
    return (
        FormJsonDiff(diff_type=u'type', path=(u'name',), old_value=u'', new_value=None),
        FormJsonDiff(diff_type=u'type', path=(u'closed_by',), old_value=u'', new_value=None),
        FormJsonDiff(diff_type=u'missing', path=(u'location_id',), old_value=Ellipsis, new_value=None),
    )

CASE_IGNORED_DIFFS = _case_ignored_diffs()
