from couchdbkit.exceptions import ResourceNotFound
from datetime import datetime

from casexml.apps.case.models import CommCareCase
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.form_processor.exceptions import AttachmentNotFound
from corehq.form_processor.interfaces.dbaccessors import (
    AbstractCaseAccessor, AbstractFormAccessor, AttachmentContent)
from couchforms.models import XFormInstance, doc_types, XFormOperation
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.parsing import json_format_datetime


class FormAccessorCouch(AbstractFormAccessor):

    @staticmethod
    def form_exists(form_id, domain=None):
        if not domain:
            return XFormInstance.get_db().doc_exist(form_id)
        else:
            try:
                xform = XFormInstance.get(form_id)
            except ResourceNotFound:
                return False

            return xform.domain == domain

    @staticmethod
    def get_form(form_id):
        return XFormInstance.get(form_id)

    @staticmethod
    def get_forms(form_ids, ordered=False):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_form_ids_in_domain_by_type(domain, type_):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_forms_by_type(domain, type_, limit, recent_first=False):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_with_attachments(form_id):
        doc = XFormInstance.get_db().get(form_id)
        doc = doc_types()[doc['doc_type']].wrap(doc)
        if doc.external_blobs:
            for name, meta in doc.external_blobs.items():
                with doc.fetch_attachment(name, stream=True) as content:
                    doc.deferred_put_attachment(
                        content,
                        name,
                        content_type=meta.content_type,
                        content_length=meta.content_length,
                    )
        else:
            # xforms are expected to at least have the XML attachment
            raise ResourceNotFound("XForm attachment missing: {}".format(form_id))
        return doc

    @staticmethod
    def get_attachment_content(form_id, attachment_id):
        return _get_attachment_content(XFormInstance, form_id, attachment_id)

    @staticmethod
    def save_new_form(form):
        form.save()

    @staticmethod
    def update_form_problem_and_state(form):
        form.save()

    @staticmethod
    def get_deleted_form_ids_for_user(domain, user_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_form_ids_for_user(domain, user_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def set_archived_state(form, archive, user_id):
        operation = "archive" if archive else "unarchive"
        form.doc_type = "XFormArchived" if archive else "XFormInstance"
        form.history.append(XFormOperation(operation=operation, user=user_id))
        # subclasses explicitly set the doc type so force regular save
        XFormInstance.save(form)

    @staticmethod
    def soft_delete_forms(domain, form_ids, deletion_date=None, deletion_id=None):
        def _form_delete(doc):
            doc['server_modified_on'] = json_format_datetime(datetime.utcnow())
        return _soft_delete(XFormInstance.get_db(), form_ids, deletion_date, deletion_id, _form_delete)

    @staticmethod
    def soft_undelete_forms(domain, form_ids):
        def _form_undelete(doc):
            doc['server_modified_on'] = json_format_datetime(datetime.utcnow())
        return _soft_undelete(XFormInstance.get_db(), form_ids, _form_undelete)

    @staticmethod
    def modify_attachment_xml_and_metadata(form_data, form_attachment_new_xml, new_username):
        # Update XML
        form_data.put_attachment(form_attachment_new_xml, name="form.xml", content_type='text/xml')
        operation = XFormOperation(user_id=SYSTEM_USER_ID, date=datetime.utcnow(),
                                   operation='gdpr_scrub')
        form_data.history.append(operation)
        # Update metadata
        form_data.form['meta']['username'] = new_username
        form_data.save()

    @staticmethod
    def iter_form_ids_by_xmlns(domain, xmlns=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")


class CaseAccessorCouch(AbstractCaseAccessor):

    @staticmethod
    def case_exists(case_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_case_ids_that_exist(domain, case_ids):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_case_xform_ids(case_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_case_ids_in_domain(domain, type=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_case_ids_in_domain_by_owners(domain, owner_ids, closed=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_open_case_ids_for_owner(domain, owner_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_closed_case_ids_for_owner(domain, owner_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_open_case_ids_in_domain_by_type(domain, case_type, owner_ids=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_case_ids_modified_with_owner_since(domain, owner_id, reference_date):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_extension_case_ids(domain, case_ids, include_closed=True, exclude_for_case_type=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_indexed_case_ids(domain, case_ids):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_reverse_indexed_cases(domain, case_ids, case_types=None, is_closed=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_last_modified_dates(domain, case_ids):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_all_reverse_indices_info(domain, case_ids):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_attachment_content(case_id, attachment_id):
        return _get_attachment_content(CommCareCase, case_id, attachment_id)

    @staticmethod
    def get_case_by_domain_hq_user_id(domain, user_id, case_type):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_cases_by_external_id(domain, external_id, case_type=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def soft_delete_cases(domain, case_ids, deletion_date=None, deletion_id=None):
        return _soft_delete(CommCareCase.get_db(), case_ids, deletion_date, deletion_id)

    @staticmethod
    def soft_undelete_cases(domain, case_ids):
        return _soft_undelete(CommCareCase.get_db(), case_ids)

    @staticmethod
    def get_deleted_case_ids_by_owner(domain, owner_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_case_owner_ids(domain):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")


def _get_attachment_content(doc_class, doc_id, attachment_id):
    try:
        doc = doc_class.get(doc_id)
        resp = doc.fetch_attachment(attachment_id, stream=True)
        content_type = doc.blobs[attachment_id].content_type
    except ResourceNotFound:
        raise AttachmentNotFound(doc_id, attachment_id)

    return AttachmentContent(content_type, resp)


def _soft_delete(db, doc_ids, deletion_date=None, deletion_id=None, custom_delete=None):
    from dimagi.utils.couch.undo import DELETED_SUFFIX
    deletion_date = json_format_datetime(deletion_date or datetime.utcnow())

    def delete(doc):
        doc['doc_type'] += DELETED_SUFFIX
        doc['-deletion_id'] = deletion_id
        doc['-deletion_date'] = deletion_date

        if custom_delete:
            custom_delete(doc)

        return doc

    return _operate_on_docs(db, doc_ids, delete)


def _soft_undelete(db, doc_ids, custom_undelete=None):
    from dimagi.utils.couch.undo import DELETED_SUFFIX

    def undelete(doc):

        doc_type = doc['doc_type']
        if doc_type.endswith(DELETED_SUFFIX):
            doc['doc_type'] = doc_type[:-len(DELETED_SUFFIX)]

        if '-deletion_id' in doc:
            del doc['-deletion_id']
        if '-deletion_date' in doc:
            del doc['-deletion_date']

        if custom_undelete:
            custom_undelete(doc)
        return doc

    return _operate_on_docs(db, doc_ids, undelete)


def _operate_on_docs(db, doc_ids, operation_fn):
    docs_to_save = []
    for doc in iter_docs(db, doc_ids):
        doc = operation_fn(doc)
        docs_to_save.append(doc)

        if len(docs_to_save) % 1000 == 0:
            db.bulk_save(docs_to_save)
            docs_to_save = []

    if docs_to_save:
        db.bulk_save(docs_to_save)

    return len(doc_ids)
