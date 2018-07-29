from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.tzmigration.timezonemigration import is_datetime_string, FormJsonDiff, json_diff

PARTIAL_DIFFS = {
    'XFormInstance*': [
        {'path': ('_rev',)},  # couch only
        {'path': ('migrating_blobs_from_couch',)},  # couch only
        {'path': ('#export_tag',)},  # couch only
        {'path': ('computed_',)},  # couch only
        {'path': ('state',)},  # SQL only
        {'path': ('computed_modified_on_',)},  # couch only
        {'path': ('deprecated_form_id',), 'old_value': Ellipsis, 'new_value': None},  # SQL always has this
        {'path': ('path',)},  # couch only
        {'path': ('user_id',)},  # couch only
        {'path': ('external_blobs',)},  # couch only
        {'diff_type': 'type', 'path': ('openrosa_headers', 'HTTP_X_OPENROSA_VERSION')},
        {'path': ('problem',), 'old_value': Ellipsis, 'new_value': None},
        {'path': ('problem',), 'old_value': '', 'new_value': None},
        {'path': ('orig_id',), 'old_value': Ellipsis, 'new_value': None},
        {'path': ('edited_on',), 'old_value': Ellipsis, 'new_value': None},
        {'path': ('repeats',), 'new_value': Ellipsis},  # report records save in form
        {'path': ('form_migrated_from_undefined_xmlns',), 'new_value': Ellipsis},
        {'diff_type': 'missing', 'old_value': None, 'new_value': Ellipsis},
    ],
    'XFormInstance': [],
    'XFormInstance-Deleted': [],
    'HQSubmission': [],
    'XFormArchived': [],
    'XFormError': [],
    'XFormDuplicate': [],
    'XFormDeprecated': [],
    'CommCareCase*': [
        {'path': ('_rev',)},  # couch only
        {'path': ('initial_processing_complete',)},  # couch only
        {'path': ('actions', '[*]')},  # ignore case actions
        {'path': ('id',)},  # SQL only
        {'path': ('@xmlns',)},  # legacy
        {'path': ('_attachments',)},  # couch only
        {'path': ('external_blobs',)},  # couch only
        {'path': ('#export_tag',)},  # couch only
        {'path': ('computed_',)},  # couch only
        {'path': ('version',)},  # couch only
        {'path': ('deleted',)},  # SQL only
        {'path': ('export_tag',)},  # couch only
        {'path': ('computed_modified_on_',)},  # couch only
        {'path': ('case_id',)},  # legacy
        {'path': ('@case_id',)},  # legacy
        {'path': ('case_json',)},  # SQL only
        {'path': ('modified_by',)},  # SQL only
        # legacy bug left cases with no owner_id
        {'diff_type': 'diff', 'path': ('owner_id',), 'old_value': ''},
        {'diff_type': 'type', 'path': ('owner_id',), 'old_value': None},
        {'diff_type': 'type', 'path': ('user_id',), 'old_value': None},
        {'diff_type': 'type', 'path': ('opened_on',), 'old_value': None},
        {'diff_type': 'type', 'path': ('opened_by',), 'old_value': Ellipsis},
        # form has case block with no actions
        {'diff_type': 'set_mismatch', 'path': ('xform_ids', '[*]'), 'old_value': ''},
        {'diff_type': 'missing', 'path': ('case_attachments',), 'old_value': Ellipsis, 'new_value': {}},
        {'diff_type': 'missing', 'old_value': None, 'new_value': Ellipsis},
    ],
    'CommCareCase': [
        # couch case was deleted and then restored - SQL case won't have deletion properties
        {'diff_type': 'missing', 'path': ('-deletion_id',), 'new_value': Ellipsis},
        {'diff_type': 'missing', 'path': ('-deletion_date',), 'new_value': Ellipsis},
    ],
    'CommCareCase-Deleted': [
        {'diff_type': 'missing', 'path': ('-deletion_id',), 'old_value': Ellipsis, 'new_value': None},
        {'diff_type': 'missing', 'path': ('-deletion_date',), 'old_value': Ellipsis, 'new_value': None},
    ],
    'CommCareCaseIndex': [
        # SQL JSON has case_id field in indices which couch JSON doesn't
        {'path': ('indices', '[*]', 'case_id')},
        # SQL indices don't have doc_type
        {
            'diff_type': 'missing', 'path': ('indices', '[*]', 'doc_type'),
            'old_value': 'CommCareCaseIndex', 'new_value': Ellipsis
        },
        # defaulted on SQL
        {
            'diff_type': 'missing', 'path': ('indices', '[*]', 'relationship'),
            'old_value': Ellipsis, 'new_value': 'child'
        },
    ],
    'LedgerValue': [
        {'path': ('_id',)},  # couch only
    ],
    'case_attachment': [
        {'path': ('doc_type',)},  # couch only
        {'path': ('attachment_properties',)},  # couch only
        {'path': ('attachment_from',)},  # couch only
        {'path': ('attachment_src',)},  # couch only
        {'path': ('content_type',)},  # couch only
        {'path': ('server_mime',)},  # couch only
        {'path': ('attachment_name',)},  # couch only
        {'path': ('server_md5',)},  # couch only
    ]
}


FORM_IGNORED_DIFFS = (
    FormJsonDiff(
        diff_type='missing', path=('history', '[*]', 'doc_type'),
        old_value='XFormOperation', new_value=Ellipsis
    ),
    FormJsonDiff(
        diff_type='diff', path=('doc_type',),
        old_value='HQSubmission', new_value='XFormInstance'
    ),
    FormJsonDiff(diff_type='missing', path=('deleted_on',), old_value=Ellipsis, new_value=None),
    FormJsonDiff(diff_type='missing', path=('location_',), old_value=[], new_value=Ellipsis),
    FormJsonDiff(diff_type='missing', path=('form', 'case', '#text'), old_value='', new_value=Ellipsis),
    FormJsonDiff(diff_type='type', path=('xmlns',), old_value=None, new_value=''),
    FormJsonDiff(diff_type='type', path=('initial_processing_complete',), old_value=None, new_value=True),
    FormJsonDiff(diff_type='missing', path=('backend_id',), old_value=Ellipsis, new_value='sql'),
)

CASE_IGNORED_DIFFS = (
    FormJsonDiff(diff_type='type', path=('name',), old_value='', new_value=None),
    FormJsonDiff(diff_type='type', path=('closed_by',), old_value='', new_value=None),
    FormJsonDiff(diff_type='missing', path=('location_id',), old_value=Ellipsis, new_value=None),
    FormJsonDiff(diff_type='missing', path=('referrals',), old_value=[], new_value=Ellipsis),
    FormJsonDiff(diff_type='missing', path=('location_',), old_value=[], new_value=Ellipsis),
    FormJsonDiff(diff_type='type', path=('type',), old_value=None, new_value=''),
    # this happens for cases where the creation form has been archived but the case still has other forms
    FormJsonDiff(diff_type='type', path=('owner_id',), old_value=None, new_value=''),
    FormJsonDiff(diff_type='missing', path=('closed_by',), old_value=Ellipsis, new_value=None),
    FormJsonDiff(diff_type='type', path=('external_id',), old_value='', new_value=None),
    FormJsonDiff(diff_type='missing', path=('deleted_on',), old_value=Ellipsis, new_value=None),
    FormJsonDiff(diff_type='missing', path=('backend_id',), old_value=Ellipsis, new_value='sql'),
)

RENAMED_FIELDS = {
    'XFormInstance': [('uid', 'instanceID')],
    'XFormDeprecated': [('deprecated_date', 'edited_on')],
    'XFormInstance-Deleted': [('-deletion_id', 'deletion_id'), ('-deletion_date', 'deleted_on')],
    'CommCareCase': [('@user_id', 'user_id'), ('@date_modified', 'modified_on')],
    'CommCareCase-Deleted': [('-deletion_id', 'deletion_id'), ('-deletion_date', 'deleted_on')],
    'case_attachment': [('attachment_size', 'content_length'), ('identifier', 'name')],
}


def filter_form_diffs(couch_form, sql_form, diffs):
    doc_type = couch_form['doc_type']
    filtered = _filter_exact_matches(diffs, FORM_IGNORED_DIFFS)
    partial_diffs = PARTIAL_DIFFS[doc_type] + PARTIAL_DIFFS['XFormInstance*']
    filtered = _filter_partial_matches(filtered, partial_diffs)
    filtered = _filter_text_xmlns(filtered)
    filtered = _filter_date_diffs(filtered)
    filtered = _filter_renamed_fields(filtered, couch_form, sql_form)
    return filtered


def _filter_text_xmlns(diffs):
    return [
        diff for diff in diffs
        if not (diff.path[-1] in ('#text', '@xmlns') and diff.old_value in ('', Ellipsis))
    ]


def filter_case_diffs(couch_case, sql_case, diffs, forms_that_touch_cases_without_actions=None):
    doc_type = couch_case['doc_type']
    filtered_diffs = _filter_exact_matches(diffs, CASE_IGNORED_DIFFS)
    partial_filters = PARTIAL_DIFFS[doc_type] + PARTIAL_DIFFS['CommCareCase*'] + PARTIAL_DIFFS['CommCareCaseIndex']
    filtered_diffs = _filter_partial_matches(filtered_diffs, partial_filters)
    filtered_diffs = _filter_date_diffs(filtered_diffs)
    filtered_diffs = _filter_user_case_diffs(couch_case, sql_case, filtered_diffs)
    filtered_diffs = _filter_xform_id_diffs(couch_case, sql_case, filtered_diffs)
    filtered_diffs = _filter_case_attachment_diffs(couch_case, sql_case, filtered_diffs)
    filtered_diffs = _filter_case_index_diffs(couch_case, sql_case, filtered_diffs)
    filtered_diffs = _filter_renamed_fields(filtered_diffs, couch_case, sql_case)
    filtered_diffs = _filter_forms_touch_case(filtered_diffs, forms_that_touch_cases_without_actions)
    return filtered_diffs


def _filter_forms_touch_case(diffs, forms_that_touch_cases_without_actions):
    """Legacy bug in case processing would not add the form ID to the list of xform_ids for the case
    if the case block had no actions"""
    if not forms_that_touch_cases_without_actions:
        return diffs

    form_id_diffs = [
        diff for diff in diffs
        if diff.diff_type == 'set_mismatch' and diff.path[0] == ('xform_ids')
    ]
    if not len(form_id_diffs):
        return diffs

    for diff in form_id_diffs:
        diffs.remove(diff)
        form_ids = diff.new_value.split(',')
        diff_ids = [form_id for form_id in form_ids if form_id not in forms_that_touch_cases_without_actions]
        if diff_ids:
            diff_dict = diff._asdict()
            diff_dict['new_value'] = ','.join(diff_ids)
            diffs.append(FormJsonDiff(**diff_dict))

    return diffs


def filter_ledger_diffs(diffs):
    return _filter_partial_matches(diffs, PARTIAL_DIFFS['LedgerValue'])


def _filter_exact_matches(diffs, diffs_to_ignore):
    filtered = []
    for diff in diffs:
        try:
            if diff not in diffs_to_ignore:
                filtered.append(diff)
        except TypeError:
            # not all diffs support hashing, do slow comparison
            diff_dict = diff._asdict()
            if not any(diff_dict == ignore._asdict() for ignore in diffs_to_ignore):
                filtered.append(diff)
    return filtered


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


def _filter_renamed_fields(diffs, couch_doc, sql_doc, doc_type_override=None):
    doc_type = doc_type_override or couch_doc['doc_type']
    if doc_type in RENAMED_FIELDS:
        renames = RENAMED_FIELDS[doc_type]
        for rename in renames:
            diffs = _check_renamed_fields(diffs, couch_doc, sql_doc, *rename)

    return diffs


def _check_renamed_fields(filtered_diffs, couch_doc, sql_doc, couch_field_name, sql_field_name):
    from corehq.apps.tzmigration.timezonemigration import FormJsonDiff
    remaining_diffs = [
        diff for diff in filtered_diffs
        if diff.path[0] != sql_field_name and diff.path[0] != couch_field_name
    ]
    if len(remaining_diffs) != len(filtered_diffs):
        sql_field = sql_doc.get(sql_field_name, Ellipsis)
        couch_field = couch_doc.get(couch_field_name, Ellipsis)
        if sql_field != couch_field \
                and not _both_dates(couch_field, sql_field) \
                and not (couch_field == Ellipsis and sql_field == ''):
            remaining_diffs.append(FormJsonDiff(
                diff_type='complex', path=(couch_field_name, sql_field_name),
                old_value=couch_field, new_value=sql_field
            ))

    return remaining_diffs


def _both_dates(old, new):
    return is_datetime_string(old) and is_datetime_string(new)


def _filter_date_diffs(diffs):
    return [
        diff for diff in diffs
        if diff.diff_type != 'diff' or not _both_dates(diff.old_value, diff.new_value)
    ]


def _filter_user_case_diffs(couch_case, sql_case, diffs):
    """SQL cases store the hq_user_id property in ``external_id`` for easier querying"""
    if 'hq_user_id' not in couch_case:
        return diffs

    filtered_diffs = [
        diff for diff in diffs
        if diff.path[0] not in ('external_id', 'hq_user_id')
    ]
    hq_user_id_couch = couch_case['hq_user_id']
    hq_user_id_sql = sql_case.get('external_id', Ellipsis)
    if hq_user_id_sql != hq_user_id_couch:
        filtered_diffs.append(FormJsonDiff(
            diff_type='complex', path=('hq_user_id', 'external_id'),
            old_value=hq_user_id_couch, new_value=hq_user_id_sql
        ))
    return filtered_diffs


def _filter_xform_id_diffs(couch_case, sql_case, diffs):
    """Some couch docs have the xform ID's out of order so assume that
    if both docs contain the same set of xform IDs then they are the same"""
    remaining_diffs = [
        diff for diff in diffs if diff.path != ('xform_ids', '[*]')
    ]
    if len(remaining_diffs) == len(diffs):
        return diffs

    ids_in_couch = set(couch_case['xform_ids'])
    ids_in_sql = set(sql_case['xform_ids'])
    if ids_in_couch ^ ids_in_sql:
        couch_only = ','.join(list(ids_in_couch - ids_in_sql))
        sql_only = ','.join(list(ids_in_sql - ids_in_couch))
        remaining_diffs.append(
            FormJsonDiff(diff_type='set_mismatch', path=('xform_ids', '[*]'), old_value=couch_only, new_value=sql_only)
        )
    else:
        remaining_diffs.append(
            FormJsonDiff(diff_type='list_order', path=('xform_ids', '[*]'), old_value=None, new_value=None)
        )

    return remaining_diffs


def _filter_case_attachment_diffs(couch_case, sql_case, diffs):
    """Attachment JSON format is different between Couch and SQL"""
    remaining_diffs = [diff for diff in diffs if diff.path[0] != 'case_attachments']
    if len(remaining_diffs) != len(diffs):
        couch_attachments = couch_case.get('case_attachments', {})
        sql_attachments = sql_case.get('case_attachments', {})

        for name, couch_att in couch_attachments.items():
            sql_att = sql_attachments.get(name, Ellipsis)
            if sql_att == Ellipsis:
                remaining_diffs.append(FormJsonDiff(
                    diff_type='missing', path=('case_attachments', name),
                    old_value=couch_att, new_value=sql_att
                ))
            else:
                att_diffs = json_diff(couch_att, sql_att)
                filtered = _filter_partial_matches(att_diffs, PARTIAL_DIFFS['case_attachment'])
                filtered = _filter_renamed_fields(filtered, couch_att, sql_att, 'case_attachment')
                for diff in filtered:
                    diff_dict = diff._asdict()
                    # convert the path back to what it should be
                    diff_dict['path'] = tuple(['case_attachments', name] + list(diff.path))
                    remaining_diffs.append(FormJsonDiff(**diff_dict))

    return remaining_diffs


def _filter_case_index_diffs(couch_case, sql_case, diffs):
    """Indices may be in different order - re-sort and compare again.
    """
    if 'indices' not in couch_case:
        return diffs

    remaining_diffs = [diff for diff in diffs if diff.path[0] != 'indices']
    if len(remaining_diffs) == len(diffs):
        return diffs

    couch_indices = couch_case['indices']
    sql_indices = sql_case['indices']

    if len(couch_indices) > 1:
        new_index_diffs = []
        couch_indices = sorted(couch_indices, key=lambda i: i['identifier'])
        sql_indices = sorted(sql_indices, key=lambda i: i['identifier'])
        for diff in json_diff(couch_indices, sql_indices, track_list_indices=False):
            diff_dict = diff._asdict()
            # convert the path back to what it should be
            diff_dict['path'] = tuple(['indices'] + list(diff.path))
            new_index_diffs.append(FormJsonDiff(**diff_dict))

        new_index_diffs = _filter_partial_matches(new_index_diffs, PARTIAL_DIFFS['CommCareCaseIndex'])
        remaining_diffs.extend(new_index_diffs)
        return remaining_diffs
    else:
        return diffs
