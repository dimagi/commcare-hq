from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
import logging
import uuid
from collections import OrderedDict

from lxml import etree

import redis
from couchdbkit.exceptions import ResourceNotFound

from casexml.apps.case import const
from casexml.apps.case.cleanup import rebuild_case_from_actions
from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from casexml.apps.case.util import get_case_xform_ids
from casexml.apps.case.xform import get_case_updates
from corehq.blobs.mixin import bulk_atomic_blobs
from corehq.form_processor.backends.couch.dbaccessors import CaseAccessorCouch
from corehq.form_processor.interfaces.processor import XFormQuestionValueIterator
from corehq.form_processor.utils import extract_meta_instance_id
from corehq.util.datadog.utils import case_load_counter, form_load_counter
from couchforms.models import (
    XFormInstance, XFormDeprecated, XFormDuplicate,
    doc_types, XFormError, SubmissionErrorLog,
    XFormOperation)
from couchforms.util import fetch_and_wrap_form
from dimagi.utils.couch import acquire_lock, release_lock
import six


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
    def copy_attachments(cls, from_form, to_form):
        for name, meta in from_form.blobs.items():
            if name != 'form.xml':
                with from_form.fetch_attachment(name, stream=True) as content:
                    to_form.deferred_put_attachment(
                        content,
                        name=name,
                        content_type=meta.content_type,
                        content_length=meta.content_length,
                    )

    @classmethod
    def copy_form_operations(cls, from_form, to_form):
        for op in from_form.history:
            to_form.history.append(op)

    @classmethod
    def new_xform(cls, form_data):
        _id = extract_meta_instance_id(form_data) or uuid.uuid4().hex
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
    def new_form_from_old(cls, existing_form, xml, value_responses_map, user_id):
        from corehq.form_processor.parsers.form import apply_deprecation
        new_form = XFormInstance.wrap(existing_form.to_json())

        for question, response in six.iteritems(value_responses_map):
            data = new_form.form_data
            i = XFormQuestionValueIterator(question)
            for (qid, repeat_index) in i:
                data = data[qid]
                if repeat_index is not None:
                    data = data[repeat_index]
            data[i.last()] = response

        new_xml = etree.tostring(xml)
        new_form._deferred_blobs = None     # will be re-populated by apply_deprecation
        new_form.external_blobs.clear()     # will be re-populated by apply_deprecation
        new_form.deferred_put_attachment(new_xml, "form.xml", content_type="text/xml")
        existing_form, new_form = apply_deprecation(existing_form, new_form)
        return (existing_form, new_form)

    @classmethod
    def save_processed_models(cls, processed_forms, cases=None, stock_result=None):
        docs = list(processed_forms)
        for form in docs:
            if form:
                form.server_modified_on = datetime.datetime.utcnow()
        docs += (cases or [])
        docs = [_f for _f in docs if _f]
        assert XFormInstance.get_db().uri == CommCareCase.get_db().uri
        with bulk_atomic_blobs(docs):
            XFormInstance.get_db().bulk_save(docs)
        if stock_result:
            stock_result.commit()

    @classmethod
    def apply_deprecation(cls, existing_xform, new_xform):
        # swap the revs
        new_xform._rev, existing_xform._rev = existing_xform._rev, new_xform._rev
        existing_xform.doc_type = XFormDeprecated.__name__
        deprecated = XFormDeprecated.wrap(existing_xform.to_json())
        assert not existing_xform.persistent_blobs, "some blobs would be lost"
        if existing_xform._deferred_blobs:
            deprecated._deferred_blobs = existing_xform._deferred_blobs.copy()

        user_id = (new_xform.auth_context and new_xform.auth_context.get('user_id')) or 'unknown'
        operation = XFormOperation(user=user_id, date=new_xform.edited_on, operation='edit')
        new_xform.history.append(operation)
        return deprecated, new_xform

    @classmethod
    def deduplicate_xform(cls, xform):
        # follow standard dupe handling, which simply saves a copy of the form
        # but a new doc_id, and a doc_type of XFormDuplicate
        xform.doc_type = XFormDuplicate.__name__
        dupe = XFormDuplicate.wrap(xform.to_json())
        assert not xform.persistent_blobs, "some blobs would be lost"
        if xform._deferred_blobs:
            dupe._deferred_blobs = xform._deferred_blobs.copy()
        dupe.problem = "Form is a duplicate of another! (%s)" % xform._id
        dupe.orig_id = xform._id
        return cls.assign_new_id(dupe)

    @classmethod
    def assign_new_id(cls, xform):
        assert not xform.persistent_blobs, "some blobs would be lost"
        xform._id = uuid.uuid4().hex
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
        # don't process error forms which are being deprecated since they were never processed in the first place.
        # see http://manage.dimagi.com/default.asp?243382
        filtered_sorted_forms = [form for form in sorted_forms if not (form.is_deprecated and form.problem)]
        touched_cases = OrderedDict()
        for xform in filtered_sorted_forms:
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
    def hard_rebuild_case(domain, case_id, detail, save=True, lock=True):
        if lock:
            # only record metric if locking since otherwise it has been
            # (most likley) recorded elsewhere
            case_load_counter("rebuild_case", domain)()
        case, lock_obj = FormProcessorCouch.get_case_with_lock(case_id, lock=lock, wrap=True)
        found = bool(case)
        if not found:
            case = CommCareCase()
            case.case_id = case_id
            case.domain = domain
            if lock:
                lock_obj = CommCareCase.get_obj_lock_by_id(case_id)
                acquire_lock(lock_obj, degrade_gracefully=False)

        try:
            assert case.domain == domain, (case.domain, domain)
            forms = FormProcessorCouch.get_case_forms(case_id)
            form_load_counter("rebuild_case", domain)(len(forms))
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
            if save:
                case.save()
            return case
        finally:
            release_lock(lock_obj, degrade_gracefully=True)

    @staticmethod
    def get_case_forms(case_id):
        """
        Get all forms that have submitted against a case (including archived and deleted forms)
        wrapped by the appropriate form type.
        """
        form_ids = get_case_xform_ids(case_id)
        return [fetch_and_wrap_form(id) for id in form_ids]

    @staticmethod
    def get_case_with_lock(case_id, lock=False, wrap=False):

        def _get_case():
            if wrap:
                return CommCareCase.get(case_id)
            else:
                return CommCareCase.get_db().get(case_id)

        try:
            if lock:
                try:
                    case, lock = CommCareCase.get_locked_obj(_id=case_id)
                    if case and not wrap:
                        case = case.to_json()
                    return case, lock
                except redis.RedisError:
                    case_doc = _get_case()
            else:
                case_doc = _get_case()
        except ResourceNotFound:
            return None, None

        return case_doc, None

    @staticmethod
    def case_exists(case_id):
        return CaseAccessorCouch.case_exists(case_id)


def _get_actions_from_forms(domain, sorted_forms, case_id):
    from corehq.form_processor.parsers.ledgers import get_stock_actions
    case_actions = []
    for form in sorted_forms:
        assert form.domain == domain, (
            "Domain mismatch on form {} referenced by case {}: {!r} != {!r}"
            .format(form.form_id, case_id, form.domain, domain)
        )

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
