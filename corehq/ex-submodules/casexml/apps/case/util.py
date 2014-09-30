from __future__ import absolute_import

from xml.etree import ElementTree
from couchdbkit.schema.properties import LazyDict
from casexml.apps.case import const
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.phone.models import SyncLogAssertionError, SyncLog
from couchforms.models import XFormInstance
from couchforms.util import create_and_lock_xform


def couchable_property(prop):
    """
    Sometimes properties that come from couch can't be put back in
    without some modification.
    """
    if isinstance(prop, LazyDict):
        return dict(prop)
    return prop


def post_case_blocks(case_blocks, form_extras=None):
    """
    Post case blocks.

    Extras is used to add runtime attributes to the form before
    sending it off to the case (current use case is sync-token pairing)
    """
    from casexml.apps.case import process_cases

    if form_extras is None:
        form_extras = {}
    form = ElementTree.Element("data")
    form.attrib['xmlns'] = "https://www.commcarehq.org/test/casexml-wrapper"
    form.attrib['xmlns:jrm'] ="http://openrosa.org/jr/xforms"
    for block in case_blocks:
        form.append(block)

    with create_and_lock_xform(ElementTree.tostring(form)) as xform:
        for k, v in form_extras.items():
            setattr(xform, k, v)
        process_cases(xform=xform)
        return xform


def reprocess_form_cases(form, config=None):
    """
    For a given form, reprocess all case elements inside it. This operation
    should be a no-op if the form was sucessfully processed, but should
    correctly inject the update into the case history if the form was NOT
    successfully processed.
    """
    from casexml.apps.case import process_cases
    process_cases(form, config)
    # mark cleaned up now that we've reprocessed it
    if form.doc_type != 'XFormInstance':
        form = XFormInstance.get(form._id)
        form.doc_type = 'XFormInstance'
        form.save()


def get_case_xform_ids(case_id):
    results = XFormInstance.get_db().view('case/form_case_index',
                                          reduce=False,
                                          startkey=[case_id],
                                          endkey=[case_id, {}])
    return list(set([row['key'][1] for row in results]))


def update_sync_log_with_checks(sync_log, xform, cases, case_id_blacklist=None):
    from casexml.apps.case.xform import CaseProcessingConfig
    case_id_blacklist = case_id_blacklist or []
    try:
        sync_log.update_phone_lists(xform, cases)
    except SyncLogAssertionError, e:
        if e.case_id and e.case_id not in case_id_blacklist:
            form_ids = get_case_xform_ids(e.case_id)
            case_id_blacklist.append(e.case_id)
            for form_id in form_ids:
                if form_id != xform._id:
                    form = XFormInstance.get(form_id)
                    if form.doc_type in ['XFormInstance', 'XFormError']:
                        reprocess_form_cases(form, CaseProcessingConfig(strict_asserts=True,
                                                                        case_id_blacklist=case_id_blacklist))
            updated_log = SyncLog.get(sync_log._id)

            update_sync_log_with_checks(updated_log, xform, cases, case_id_blacklist=case_id_blacklist)


def reverse_indices(db, case):
    return db.view("case/related",
        key=[case.domain, case._id, "reverse_index"],
        reduce=False,
        wrapper=lambda r: CommCareCaseIndex.wrap(r['value'])
    ).all()


def primary_actions(case):
    return filter(lambda a: a.action_type != const.CASE_ACTION_REBUILD,
                  case.actions)
