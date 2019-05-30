from __future__ import absolute_import
from __future__ import unicode_literals

from collections import defaultdict
from itertools import chain

from memoized import memoized

from corehq.apps.tzmigration.timezonemigration import is_datetime_string, FormJsonDiff, json_diff, MISSING

from .diffrule import Ignore


load_ignore_rules = memoized(lambda: {
    'XFormInstance*': [
        Ignore(path='_rev', new=MISSING),
        Ignore(path='migrating_blobs_from_couch', new=MISSING),
        Ignore(path='#export_tag', new=MISSING),
        Ignore(path='computed_', new=MISSING),
        Ignore(path='state', old=MISSING),
        Ignore(path='computed_modified_on_', new=MISSING),
        Ignore(path='deprecated_form_id', old=MISSING, new=None),
        Ignore(path='path', new=MISSING),
        Ignore(path='user_id', old=MISSING),
        Ignore(path='external_blobs', new=MISSING),
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
        Ignore('missing', 'location_', new=MISSING),
        Ignore('type', 'xmlns', old=None, new=''),
        Ignore('type', 'initial_processing_complete', old=None, new=True),
        Ignore('missing', 'backend_id', old=MISSING, new='sql'),
        Ignore('missing', 'location_id', new=MISSING, check=is_supply_point),
        Ignore('missing', '_attachments', new=MISSING),

        Ignore('diff', check=has_date_values),
        Ignore(check=is_text_xmlns),
    ],
    'XFormInstance': [
        ignore_renamed('uid', 'instanceID'),
    ],
    'XFormInstance-Deleted': [
        ignore_renamed('-deletion_id', 'deletion_id'),
        ignore_renamed('-deletion_date', 'deleted_on'),
    ],
    'HQSubmission': [],
    'XFormArchived': [],
    'XFormError': [],
    'XFormDuplicate': [],
    'XFormDeprecated': [
        ignore_renamed('deprecated_date', 'edited_on'),
    ],
    'CommCareCase*': [
        Ignore(path='_rev', new=MISSING),
        Ignore(path='initial_processing_complete', new=MISSING),
        Ignore(check=is_case_actions),  # ignore case actions
        Ignore(path='id', old=MISSING),
        Ignore(path='@xmlns'),  # legacy
        Ignore(path='_attachments', new=MISSING),
        Ignore(path='external_blobs', new=MISSING),
        Ignore(path='#export_tag', new=MISSING),
        Ignore(path='computed_', new=MISSING),
        Ignore(path='version', new=MISSING),
        Ignore(path='deleted', old=MISSING),
        Ignore(path='export_tag', new=MISSING),
        Ignore(path='computed_modified_on_', new=MISSING),
        Ignore(path='case_id'),  # legacy
        Ignore(path='@case_id'),  # legacy
        Ignore(path='case_json', old=MISSING),
        Ignore(path='modified_by', old=MISSING),
        # legacy bug left cases with no owner_id
        Ignore('diff', 'owner_id', old=''),
        Ignore('type', 'owner_id', old=None),
        Ignore('type', 'user_id', old=None),
        Ignore('type', 'opened_on', old=None),
        Ignore('type', 'opened_by', old=MISSING),
        # The form that created the case was archived, but the opened_by
        # field was not updated as part of the subsequent rebuild.
        # `CouchCaseUpdateStrategy.reset_case_state()` does not reset
        # opened_by or opened_on (the latter is ignored by has_date_values).
        Ignore('diff', 'opened_by', check=is_case_without_create_action),
        # form has case block with no actions
        Ignore('set_mismatch', ('xform_ids', '[*]'), old=''),
        Ignore('missing', 'case_attachments', old=MISSING, new={}),
        Ignore('missing', old=None, new=MISSING),

        # CASE_IGNORED_DIFFS
        Ignore('type', 'name', old='', new=None),
        Ignore('type', 'closed_by', old='', new=None),
        Ignore('missing', 'location_id', old=MISSING, new=None),
        Ignore('missing', 'referrals', new=MISSING),
        Ignore('missing', 'location_', new=MISSING),
        Ignore('type', 'type', old=None, new=''),
        # this happens for cases where the creation form has been archived but the case still has other forms
        Ignore('type', 'owner_id', old=None, new=''),
        Ignore('missing', 'closed_by', old=MISSING, new=None),
        Ignore('type', 'external_id', old='', new=None),
        Ignore('missing', 'deleted_on', old=MISSING, new=None),
        Ignore('missing', 'backend_id', old=MISSING, new='sql'),

        Ignore(path=('indices', '[*]', 'case_id'), old=MISSING),
        Ignore('missing', ('indices', '[*]', 'doc_type'), old='CommCareCaseIndex', new=MISSING),
        Ignore('missing', ('indices', '[*]', 'relationship'), old=MISSING, new='child'),  # defaulted on SQL

        Ignore(path=('actions', '[*]')),

        Ignore('diff', check=has_date_values),
        ignore_renamed('hq_user_id', 'external_id'),
        Ignore(path=('xform_ids', '[*]'), check=xform_ids_order),
        Ignore(check=case_attachments),
        Ignore(check=case_index_order),
    ],
    'CommCareCase': [
        # couch case was deleted and then restored - SQL case won't have deletion properties
        Ignore('missing', '-deletion_id', new=MISSING),
        Ignore('missing', '-deletion_date', new=MISSING),

        ignore_renamed('@user_id', 'user_id'),
        ignore_renamed('@date_modified', 'modified_on'),
    ],
    'CommCareCase-Deleted': [
        Ignore('missing', '-deletion_id', old=MISSING, new=None),
        Ignore('missing', 'deletion_id', old=MISSING, new=None),
        Ignore('complex', ('-deletion_id', 'deletion_id'), old=MISSING, new=None),
        Ignore('missing', '-deletion_date', old=MISSING, new=None),
        Ignore('missing', 'deleted_on', old=MISSING),
        ignore_renamed('-deletion_id', 'deletion_id'),
        ignore_renamed('-deletion_date', 'deleted_on'),
    ],
    'LedgerValue': [
        Ignore(path='_id'),  # couch != SQL
    ],
    'case_attachment': [
        Ignore(path='attachment_properties', new=MISSING),
        Ignore(path='attachment_from', new=MISSING),
        Ignore(path='attachment_src', new=MISSING),
        Ignore(path='content_type', old=MISSING),
        Ignore(path='doc_type', new=MISSING),
        Ignore(path='server_mime', new=MISSING),
        Ignore(path='attachment_name', new=MISSING),
        Ignore(path='server_md5', new=MISSING),
        ignore_renamed('attachment_size', 'content_length'),
        ignore_renamed('identifier', 'name'),
    ]
})


def filter_form_diffs(couch_form, sql_form, diffs):
    doc_type = couch_form['doc_type']
    return _filter_ignored(couch_form, sql_form, diffs, [doc_type, 'XFormInstance*'])


def filter_case_diffs(couch_case, sql_case, diffs, forms_that_touch_cases_without_actions=None):
    doc_type = couch_case['doc_type']
    doc_types = [doc_type, 'CommCareCase*']
    diffs = _filter_ignored(couch_case, sql_case, diffs, doc_types)
    if forms_that_touch_cases_without_actions:
        diffs = _filter_forms_touch_case(diffs, forms_that_touch_cases_without_actions)
    return diffs


def _filter_forms_touch_case(diffs, forms_that_touch_cases_without_actions):
    """Legacy bug in case processing would not add the form ID to the list of
    xform_ids for the case if the case block had no actions"""
    other_diffs = []
    form_id_diffs = []
    for diff in diffs:
        if diff.diff_type == 'set_mismatch' and diff.path[0] == 'xform_ids':
            form_id_diffs.append(diff)
        else:
            other_diffs.append(diff)

    if form_id_diffs:
        diffs = other_diffs
        for diff in form_id_diffs:
            form_ids = diff.new_value.split(',')
            diff_ids = [
                form_id for form_id in form_ids
                if form_id not in forms_that_touch_cases_without_actions
            ]
            if diff_ids:
                diff = diff._replace(new_value=','.join(diff_ids))
                diffs.append(diff)

    return diffs


def filter_ledger_diffs(diffs):
    return _filter_ignored(None, None, diffs, ['LedgerValue'])


def _filter_ignored(couch_obj, sql_obj, diffs, doc_types):
    """Filter out diffs that match ignore rules

    :param doc_types: List of doc type specifiers (`load_ignore_rules()` keys).
    """
    ignore_rules = _get_ignore_rules(tuple(doc_types))
    return list(_filter_diffs(diffs, ignore_rules, couch_obj, sql_obj))


def _filter_diffs(diffs, ignore_rules, old_obj, new_obj):
    seen = set()
    any_path_rules = ignore_rules.get(ANY_PATH, [])
    for diff in diffs:
        for rule in chain(ignore_rules.get(diff.path, []), any_path_rules):
            try:
                match = rule.matches(diff, old_obj, new_obj)
            except ReplaceDiff as replacement:
                match = True
                for new_diff in replacement.diffs:
                    key = (new_diff.diff_type, new_diff.path)
                    if key not in seen:
                        seen.add(key)
                        yield new_diff
            if match:
                break
        else:
            yield diff


@memoized
def _get_ignore_rules(doc_types):
    """Get ignore rules by path for the given doc type specifiers

    This is an optimization to minimize M in O(N * M) nested loop in
    `_filter_diffs()`. Note very important `@memoized` decorator.

    :returns: A dict of lists of ignore rules:
    ```
    {
        <path>: [<Ignore>, ...],
        ...,
        ANY_PATH: [<Ignore>, ...]  # rules with unhashable path
    }
    ```
    """
    ignore_rules = defaultdict(list)
    for typespec in doc_types:
        for rule in load_ignore_rules()[typespec]:
            try:
                ignore_rules[rule.path].append(rule)
            except TypeError:
                ignore_rules[ANY_PATH].append(rule)
    return dict(ignore_rules)


ANY_PATH = object()


class ReplaceDiff(Exception):

    def __init__(self, diffs=None, **kw):
        if diffs is None:
            kw.setdefault("diff_type", "complex")
            kw.setdefault("old_value", None)
            kw.setdefault("new_value", None)
            self.diffs = [FormJsonDiff(**kw)]
        else:
            assert not kw, 'diffs and kw not allowed together'
            self.diffs = diffs


def is_case_actions(old_obj, new_obj, rule, diff):
    return diff.path[0] == "actions"


def ignore_renamed(old_name, new_name):
    def is_renamed(old_obj, new_obj, rule, diff):
        diffname = diff.path[0]
        if diffname == old_name or diffname == new_name:
            old_value = old_obj.get(old_name, MISSING)
            new_value = new_obj.get(new_name, MISSING)
            if old_value is not MISSING and new_value is not MISSING:
                if old_value != new_value and not _both_dates(new_value, old_value):
                    raise ReplaceDiff(
                        path=(old_name, new_name),
                        old_value=old_value,
                        new_value=new_value,
                    )
                return True
        return False

    return Ignore(check=is_renamed)


def has_date_values(old_obj, new_obj, rule, diff):
    return _both_dates(diff.old_value, diff.new_value)


def is_text_xmlns(old_obj, new_obj, rule, diff):
    return diff.path[-1] in ('#text', '@xmlns') and diff.old_value in ('', MISSING)


def _both_dates(old, new):
    return is_datetime_string(old) and is_datetime_string(new)


def xform_ids_order(old_obj, new_obj, rule, diff):
    """Some couch docs have the xform ID's out of order

    `sql_case.xform_ids` is derived from transactions, which are sorted
    by `server_date`. `couch_case.xform_ids` is based on couch actions,
    which are not necessarily sorted by `server_date`. Therefore it is
    likely that they will not match, even after rebuilding either side.

    `reconcile_transactions` does not update `transaction.server_date`
    and therefore SORT_OUT_OF_ORDER_FORM_SUBMISSIONS_SQL is not useful
    to eliminate `sql_case.xform_ids` list order diffs.
    """
    old_ids = set(old_obj['xform_ids'])
    new_ids = set(new_obj['xform_ids'])
    if old_ids ^ new_ids:
        raise ReplaceDiff(
            diff_type="set_mismatch",
            path=('xform_ids', '[*]'),
            old_value=','.join(list(old_ids - new_ids)),
            new_value=','.join(list(new_ids - old_ids)),
        )
    return True


def case_attachments(old_obj, new_obj, rule, original_diff):
    """Attachment JSON format is different between Couch and SQL"""
    if original_diff.path[0] != "case_attachments":
        return False
    diffs = []
    old_attachments = old_obj.get("case_attachments", {})
    new_attachments = new_obj.get("case_attachments", {})
    for name in set(old_attachments) | set(new_attachments):
        old_att = old_attachments.get(name, MISSING)
        new_att = new_attachments.get(name, MISSING)
        if old_att is MISSING or new_att is MISSING:
            diffs.append(FormJsonDiff(
                diff_type='missing', path=('case_attachments', name),
                old_value=old_att, new_value=new_att,
            ))
        else:
            att_diffs = json_diff(old_att, new_att)
            for diff in _filter_ignored(old_att, new_att, att_diffs, ['case_attachment']):
                # convert the path back to what it should be
                diff = diff._replace(path=('case_attachments', name) + diff.path)
                diffs.append(diff)
    if diffs:
        raise ReplaceDiff(diffs)
    return True


def _filter_case_action_diffs(diffs):
    """Ignore all case action diffs"""
    return [
        diff for diff in diffs
        if diff.path[0] != 'actions'
    ]


def case_index_order(old_obj, new_obj, rule, diff):
    """Attachment order may be different between Couch and SQL"""
    if diff.path[0] != "indices" or len(old_obj['indices']) < 2:
        return False

    def key(index):
        return index['identifier']

    diffs = []
    old_indices = sorted(old_obj['indices'], key=key)
    new_indices = sorted(new_obj['indices'], key=key)
    for diff in json_diff(old_indices, new_indices, track_list_indices=False):
        # convert the path back to what it should be
        diff = diff._replace(path=('indices',) + diff.path)
        diffs.append(diff)
    if diffs:
        raise ReplaceDiff(diffs)
    return True


def is_supply_point(old_obj, new_obj, rule, diff):
    from corehq.apps.commtrack.const import COMMTRACK_SUPPLY_POINT_XMLNS
    return old_obj["xmlns"] == COMMTRACK_SUPPLY_POINT_XMLNS


def is_case_without_create_action(old_obj, new_obj, rule, diff):
    from casexml.apps.case.const import CASE_ACTION_CREATE as CREATE
    return all(a.get("action_type") != CREATE for a in old_obj.get("actions", []))
