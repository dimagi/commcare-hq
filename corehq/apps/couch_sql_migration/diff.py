from __future__ import absolute_import
from __future__ import unicode_literals

from itertools import chain

from corehq.apps.tzmigration.timezonemigration import is_datetime_string, FormJsonDiff, json_diff, MISSING

from .diffrule import Ignore


IGNORE_RULES = {
    'XFormInstance*': [
        Ignore(path='_rev'),  # couch only
        Ignore(path='migrating_blobs_from_couch'),  # couch only
        Ignore(path='#export_tag'),  # couch only
        Ignore(path='computed_'),  # couch only
        Ignore(path='state'),  # SQL only
        Ignore(path='computed_modified_on_'),  # couch only
        Ignore(path='deprecated_form_id', old=MISSING, new=None),  # SQL always has this
        Ignore(path='path'),  # couch only
        Ignore(path='user_id'),  # couch only
        Ignore(path='external_blobs'),  # couch only
        Ignore(type='type', path=('openrosa_headers', 'HTTP_X_OPENROSA_VERSION')),
        Ignore(path='problem', old=MISSING, new=None),
        Ignore(path='problem', old='', new=None),
        Ignore(path='orig_id', old=MISSING, new=None),
        Ignore(path='edited_on', old=MISSING, new=None),
        Ignore(path='repeats', old=MISSING),  # report records save in form
        Ignore(path='form_migrated_from_undefined_xmlns', new=MISSING),
        Ignore(type='missing', old=None, new=MISSING),

        # FORM_IGNORED_DIFFS
        Ignore('missing', ('history', '[*]', 'doc_type'), old='XFormOperation', new=MISSING),
        Ignore('diff', 'doc_type', old='HQSubmission', new='XFormInstance'),
        Ignore('missing', 'deleted_on', old=MISSING, new=None),
        Ignore('missing', 'location_', old=[], new=MISSING),
        Ignore('missing', ('form', 'case', '#text'), old='', new=MISSING),
        Ignore('type', 'xmlns', old=None, new=''),
        Ignore('type', 'initial_processing_complete', old=None, new=True),
        Ignore('missing', 'backend_id', old=MISSING, new='sql'),
    ],
    'XFormInstance': [],
    'XFormInstance-Deleted': [],
    'HQSubmission': [],
    'XFormArchived': [],
    'XFormError': [],
    'XFormDuplicate': [],
    'XFormDeprecated': [],
    'CommCareCase*': [
        Ignore(path='_rev'),  # couch only
        Ignore(path='initial_processing_complete'),  # couch only
        Ignore(path=('actions', '[*]')),  # ignore case actions
        Ignore(path='id'),  # SQL only
        Ignore(path='@xmlns'),  # legacy
        Ignore(path='_attachments'),  # couch only
        Ignore(path='external_blobs'),  # couch only
        Ignore(path='#export_tag'),  # couch only
        Ignore(path='computed_'),  # couch only
        Ignore(path='version'),  # couch only
        Ignore(path='deleted'),  # SQL only
        Ignore(path='export_tag'),  # couch only
        Ignore(path='computed_modified_on_'),  # couch only
        Ignore(path='case_id'),  # legacy
        Ignore(path='@case_id'),  # legacy
        Ignore(path='case_json'),  # SQL only
        Ignore(path='modified_by'),  # SQL only
        # legacy bug left cases with no owner_id
        Ignore('diff', 'owner_id', old=''),
        Ignore('type', 'owner_id', old=None),
        Ignore('type', 'user_id', old=None),
        Ignore('type', 'opened_on', old=None),
        Ignore('type', 'opened_by', old=MISSING),
        # form has case block with no actions
        Ignore('set_mismatch', ('xform_ids', '[*]'), old=''),
        Ignore('missing', 'case_attachments', old=MISSING, new={}),
        Ignore('missing', old=None, new=MISSING),

        # CASE_IGNORED_DIFFS
        Ignore('type', 'name', old='', new=None),
        Ignore('type', 'closed_by', old='', new=None),
        Ignore('missing', 'location_id', old=MISSING, new=None),
        Ignore('missing', 'referrals', old=[], new=MISSING),
        Ignore('missing', 'location_', old=[], new=MISSING),
        Ignore('type', 'type', old=None, new=''),
        # this happens for cases where the creation form has been archived but the case still has other forms
        Ignore('type', 'owner_id', old=None, new=''),
        Ignore('missing', 'closed_by', old=MISSING, new=None),
        Ignore('type', 'external_id', old='', new=None),
        Ignore('missing', 'deleted_on', old=MISSING, new=None),
        Ignore('missing', 'backend_id', old=MISSING, new='sql'),
    ],
    'CommCareCase': [
        # couch case was deleted and then restored - SQL case won't have deletion properties
        Ignore('missing', '-deletion_id', new=MISSING),
        Ignore('missing', '-deletion_date', new=MISSING),
    ],
    'CommCareCase-Deleted': [
        Ignore('missing', '-deletion_id', old=MISSING, new=None),
        Ignore('complex', ('-deletion_id', 'deletion_id'), old=MISSING, new=None),
        Ignore('missing', '-deletion_date', old=MISSING, new=None),
    ],
    'CommCareCaseIndex': [
        # SQL JSON has case_id field in indices which couch JSON doesn't
        Ignore(path=('indices', '[*]', 'case_id')),
        # SQL indices don't have doc_type
        Ignore('missing', ('indices', '[*]', 'doc_type'), old='CommCareCaseIndex', new=MISSING),
        # defaulted on SQL
        Ignore('missing', ('indices', '[*]', 'relationship'), old=MISSING, new='child'),
    ],
    'LedgerValue': [
        Ignore(path='_id'),  # couch only
    ],
    'case_attachment': [
        Ignore(path='_id'),  # couch only
        Ignore(path='attachment_properties'),  # couch only
        Ignore(path='attachment_from'),  # couch only
        Ignore(path='attachment_src'),  # couch only
        Ignore(path='content_type'),  # couch only
        Ignore(path='server_mime'),  # couch only
        Ignore(path='attachment_name'),  # couch only
        Ignore(path='server_md5'),  # couch only
    ]
}


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
    filtered = _filter_ignored(couch_form, sql_form, diffs, [doc_type, 'XFormInstance*'])
    filtered = _filter_text_xmlns(filtered)
    filtered = _filter_date_diffs(filtered)
    filtered = _filter_renamed_fields(filtered, couch_form, sql_form)
    return filtered


def _filter_text_xmlns(diffs):
    return [
        diff for diff in diffs
        if not (diff.path[-1] in ('#text', '@xmlns') and diff.old_value in ('', MISSING))
    ]


def filter_case_diffs(couch_case, sql_case, diffs, forms_that_touch_cases_without_actions=None):
    doc_type = couch_case['doc_type']
    doc_types = [doc_type, 'CommCareCase*', 'CommCareCaseIndex']
    filtered_diffs = _filter_ignored(couch_case, sql_case, diffs, doc_types)
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
    return _filter_ignored(None, None, diffs, ['LedgerValue'])


def _filter_ignored(couch_obj, sql_obj, diffs, doc_types):
    """Filter out diffs that match ignore rules

    :param doc_types: List of doc type specifiers (IGNORE_RULES keys).
    """
    ignore_rules = list(chain.from_iterable(
        IGNORE_RULES.get(d, []) for d in doc_types
    ))
    return [
        diff for diff in diffs
        if not any(rule.matches(diff, couch_obj, sql_obj) for rule in ignore_rules)
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
        sql_field = sql_doc.get(sql_field_name, MISSING)
        couch_field = couch_doc.get(couch_field_name, MISSING)
        if sql_field != couch_field \
                and not _both_dates(couch_field, sql_field) \
                and not (couch_field is MISSING and sql_field == ''):
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
    hq_user_id_sql = sql_case.get('external_id', MISSING)
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
            sql_att = sql_attachments.get(name, MISSING)
            if sql_att is MISSING:
                remaining_diffs.append(FormJsonDiff(
                    diff_type='missing', path=('case_attachments', name),
                    old_value=couch_att, new_value=sql_att
                ))
            else:
                att_diffs = json_diff(couch_att, sql_att)
                filtered = _filter_ignored(couch_att, sql_att, att_diffs, ['case_attachment'])
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

        new_index_diffs = _filter_ignored(
            couch_case,
            sql_case,
            new_index_diffs,
            ['CommCareCaseIndex'],
        )
        remaining_diffs.extend(new_index_diffs)
        return remaining_diffs
    else:
        return diffs
