import datetime
import logging

from couchdbkit.exceptions import ResourceNotFound

from casexml.apps.case import const
from casexml.apps.case.cleanup import rebuild_case_from_actions
from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from casexml.apps.case.util import get_case_xform_ids
from casexml.apps.case.xform import get_case_updates
from corehq.form_processor.exceptions import CaseNotFound
from couchforms.util import fetch_and_wrap_form
from couchforms.models import (
    XFormInstance, XFormDeprecated, XFormDuplicate,
    doc_types, XFormError, SubmissionErrorLog
)
from corehq.form_processor.utils import extract_meta_instance_id


class FormProcessorCouch(object):

    @classmethod
    def store_attachments(cls, xform, attachments):
        for attachment in attachments:
            xform.deferred_put_attachment(
                attachment.content,
                attachment.name,
                content_type=attachment.content_type,
            )

    @classmethod
    def new_xform(cls, form_data):
        _id = extract_meta_instance_id(form_data) or XFormInstance.get_db().server.next_uuid()
        assert _id
        xform = XFormInstance(
            # form has to be wrapped
            {'form': form_data},
            # other properties can be set post-wrap
            _id=_id,
            xmlns=form_data.get('@xmlns'),
            received_on=datetime.datetime.utcnow(),
        )
        return xform

    @classmethod
    def is_duplicate(cls, xform_id, domain=None):
        if domain:
            try:
                existing_doc = XFormInstance.get_db().get(xform_id)
            except ResourceNotFound:
                return False
            return existing_doc.get('domain') == domain and existing_doc.get('doc_type') in doc_types()
        else:
            return xform_id in XFormInstance.get_db()

    @classmethod
    def hard_delete_case_and_forms(cls, domain, case, xforms):
        docs = [case._doc] + [f._doc for f in xforms]
        case.get_db().bulk_delete(docs)

    @classmethod
    def save_processed_models(cls, processed_forms, cases=None, stock_result=None):
        docs = list(processed_forms) + (cases or [])
        docs = filter(None, docs)
        assert XFormInstance.get_db().uri == CommCareCase.get_db().uri
        XFormInstance.get_db().bulk_save(docs)
        if stock_result:
            stock_result.commit()

    @classmethod
    def apply_deprecation(cls, existing_xform, new_xform):
        # swap the revs
        new_xform._rev, existing_xform._rev = existing_xform._rev, new_xform._rev
        existing_xform.doc_type = XFormDeprecated.__name__
        return XFormDeprecated.wrap(existing_xform.to_json()), new_xform

    @classmethod
    def deduplicate_xform(cls, xform):
        # follow standard dupe handling, which simply saves a copy of the form
        # but a new doc_id, and a doc_type of XFormDuplicate
        xform.doc_type = XFormDuplicate.__name__
        dupe = XFormDuplicate.wrap(xform.to_json())
        dupe.problem = "Form is a duplicate of another! (%s)" % xform._id
        return cls.assign_new_id(dupe)

    @classmethod
    def assign_new_id(cls, xform):
        new_id = XFormInstance.get_db().server.next_uuid()
        xform._id = new_id
        return xform

    @classmethod
    def xformerror_from_xform_instance(self, instance, error_message, with_new_id=False):
        return XFormError.from_xform_instance(instance, error_message, with_new_id=with_new_id)

    @classmethod
    def submission_error_form_instance(cls, domain, instance, message):
        log = SubmissionErrorLog.from_instance(instance, message)
        log.domain = domain
        return log

    @staticmethod
    def get_cases_from_forms(case_db, xforms):
        """Get all cases affected by the forms. Includes new cases, updated cases.
        """
        # have to apply the deprecations before the updates
        sorted_forms = sorted(xforms, key=lambda f: 0 if f.is_deprecated else 1)
        touched_cases = {}
        for xform in sorted_forms:
            for case_update in get_case_updates(xform):
                case_update_meta = case_db.get_case_from_case_update(case_update, xform)
                if case_update_meta.case:
                    touched_cases[case_update_meta.case.case_id] = case_update_meta
                else:
                    logging.error(
                        "XForm %s had a case block that wasn't able to create a case! "
                        "This usually means it had a missing ID" % xform.get_id
                    )

        return touched_cases

    @staticmethod
    def hard_rebuild_case(domain, case_id, detail):
        try:
            case = CommCareCase.get(case_id)
            assert case.domain == domain
            found = True
        except CaseNotFound:
            case = CommCareCase()
            case.case_id = case_id
            case.domain = domain
            found = False

        forms = FormProcessorCouch.get_case_forms(case_id)
        filtered_forms = [f for f in forms if f.is_normal]
        sorted_forms = sorted(filtered_forms, key=lambda f: f.received_on)

        actions = _get_actions_from_forms(domain, sorted_forms, case_id)

        if not found and case.domain is None:
            case.domain = domain

        rebuild_case_from_actions(case, actions)
        # todo: should this move to case.rebuild?
        if not case.xform_ids:
            if not found:
                return None
            # there were no more forms. 'delete' the case
            case.doc_type = 'CommCareCase-Deleted'

        # add a "rebuild" action
        case.actions.append(_rebuild_action())
        case.save()
        return case

    @staticmethod
    def get_case_forms(case_id):
        """
        Get all forms that have submitted against a case (including archived and deleted forms)
        wrapped by the appropriate form type.
        """
        form_ids = get_case_xform_ids(case_id)
        return [fetch_and_wrap_form(id) for id in form_ids]


def _get_actions_from_forms(domain, sorted_forms, case_id):
    from corehq.form_processor.parsers.ledgers import get_stock_actions
    case_actions = []
    for form in sorted_forms:
        assert form.domain == domain

        case_updates = get_case_updates(form)
        filtered_updates = [u for u in case_updates if u.id == case_id]
        for u in filtered_updates:
            case_actions.extend(u.get_case_actions(form))
        stock_actions = get_stock_actions(form)
        case_actions.extend([intent.get_couch_action()
                             for intent in stock_actions.case_action_intents
                             if not intent.is_deprecation])
    return case_actions


def _rebuild_action():
    now = datetime.datetime.utcnow()
    return CommCareCaseAction(
        action_type=const.CASE_ACTION_REBUILD,
        date=now,
        server_date=now,
    )
