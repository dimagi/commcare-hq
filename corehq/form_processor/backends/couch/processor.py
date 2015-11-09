import logging
import datetime

from couchdbkit import BulkSaveError

from casexml.apps.case.models import CommCareCase
from couchforms.util import process_xform, _handle_unexpected_error, deprecation_type
from couchforms.models import XFormInstance, XFormDeprecated, doc_types
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
        try:
            XFormInstance.get_db().bulk_save(docs)
        except BulkSaveError as e:
            logging.error('BulkSaveError saving forms', exc_info=1,
                          extra={'details': {'errors': e.errors}})
            raise
        except Exception as e:
            docs_being_saved = [doc['_id'] for doc in docs]
            error_message = u'Unexpected error bulk saving docs {}: {}, doc_ids: {}'.format(
                type(e).__name__,
                unicode(e),
                ', '.join(docs_being_saved)
            )
            instance = _handle_unexpected_error(instance, error_message)
            raise

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
    def assign_new_id(cls, xform):
        new_id = XFormInstance.get_db().server.next_uuid()
        xform._id = new_id
        return xform

    @classmethod
    def should_handle_as_duplicate_or_edit(cls, xform_id, domain):
        existing_doc = XFormInstance.get_db().get(xform_id)
        return existing_doc.get('domain') == domain and existing_doc.get('doc_type') in doc_types()
