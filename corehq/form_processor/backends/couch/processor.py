import datetime
import logging

from casexml.apps.case import const
from casexml.apps.case.cleanup import get_case_forms, rebuild_case_from_actions
from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from casexml.apps.case.xform import get_case_updates
from corehq.form_processor.exceptions import CaseNotFound
from couchforms.util import process_xform, deprecation_type
from couchforms.models import XFormInstance, XFormDeprecated, XFormDuplicate, doc_types, XFormError
from corehq.util.couch_helpers import CouchAttachmentsBuilder
from corehq.form_processor.utils import extract_meta_instance_id


class FormProcessorCouch(object):

    @classmethod
    def post_xform(cls, instance_xml, attachments=None, process=None, domain='test-domain'):
        """
        create a new xform and releases the lock

        this is a testing entry point only and is not to be used in real code

        """
        if not process:
            def process(xform):
                xform.domain = domain
        xform_lock = process_xform(instance_xml, attachments=attachments, process=process, domain=domain)
        with xform_lock as xforms:
            for xform in xforms:
                xform.save()
            return xforms[0]

    @classmethod
    def store_attachments(cls, xform, attachments):
        builder = CouchAttachmentsBuilder()
        for attachment in attachments:
            builder.add(
                content=attachment.content,
                name=attachment.name,
                content_type=attachment.content_type,
            )

        xform._attachments = builder.to_json()

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
    def is_duplicate(cls, xform):
        return xform.form_id in XFormInstance.get_db()

    @classmethod
    def bulk_save(cls, instance, xforms, cases=None):
        docs = xforms + (cases or [])
        assert XFormInstance.get_db().uri == CommCareCase.get_db().uri
        XFormInstance.get_db().bulk_save(docs)

    @classmethod
    def process_stock(cls, xforms, case_db):
        from corehq.apps.commtrack.processing import process_stock
        return process_stock(xforms, case_db)

    @classmethod
    def deprecate_xform(cls, existing_xform, new_xform):
        # if the form contents are not the same:
        #  - "Deprecate" the old form by making a new document with the same contents
        #    but a different ID and a doc_type of XFormDeprecated
        #  - Save the new instance to the previous document to preserve the ID

        old_id = existing_xform._id
        new_xform = cls.assign_new_id(new_xform)

        # swap the two documents so the original ID now refers to the new one
        # and mark original as deprecated
        new_xform._id, existing_xform._id = old_id, new_xform._id
        new_xform._rev, existing_xform._rev = existing_xform._rev, new_xform._rev

        # flag the old doc with metadata pointing to the new one
        existing_xform.doc_type = deprecation_type()
        existing_xform.orig_id = old_id

        # and give the new doc server data of the old one and some metadata
        new_xform.received_on = existing_xform.received_on
        new_xform.deprecated_form_id = existing_xform._id
        new_xform.edited_on = datetime.datetime.utcnow()
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
    def should_handle_as_duplicate_or_edit(cls, xform_id, domain):
        existing_doc = XFormInstance.get_db().get(xform_id)
        return existing_doc.get('domain') == domain and existing_doc.get('doc_type') in doc_types()

    @classmethod
    def xformerror_from_xform_instance(self, instance, error_message, with_new_id=False):
        return XFormError.from_xform_instance(instance, error_message, with_new_id=with_new_id)

    @staticmethod
    def get_cases_from_forms(case_db, xforms):
        """Get all cases affected by the forms. Includes new cases, updated cases.
        """
        # have to apply the deprecations before the updates
        sorted_forms = sorted(xforms, key=lambda f: 0 if f.is_deprecated else 1)
        touched_cases = {}
        for xform in sorted_forms:
            for case_update in get_case_updates(xform):
                case_doc = case_db.get_case_from_case_update(case_update, xform)
                if case_doc:
                    touched_cases[case_doc.case_id] = case_doc
                else:
                    logging.error(
                        "XForm %s had a case block that wasn't able to create a case! "
                        "This usually means it had a missing ID" % xform.get_id
                    )

        return touched_cases

    @staticmethod
    def hard_rebuild_case(domain, case_id):
        try:
            case = CommCareCase.get(case_id)
            assert case.domain == domain
            found = True
        except CaseNotFound:
            case = CommCareCase()
            case.case_id = case_id
            case.domain = domain
            found = False

        forms = get_case_forms(case_id)
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


def _get_actions_from_forms(domain, sorted_forms, case_id):
    from corehq.apps.commtrack.processing import get_stock_actions
    case_actions = []
    for form in sorted_forms:
        assert form.domain == domain

        case_updates = get_case_updates(form)
        filtered_updates = [u for u in case_updates if u.id == case_id]
        for u in filtered_updates:
            case_actions.extend(u.get_case_actions(form))
        stock_actions = get_stock_actions(form)
        case_actions.extend([intent.action
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
