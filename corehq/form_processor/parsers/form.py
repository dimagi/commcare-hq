import hashlib

import datetime

from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import Attachment
from corehq.form_processor.utils import convert_xform_to_json, adjust_datetimes
from couchforms import XMLSyntaxError
from couchforms.exceptions import DuplicateError
from dimagi.utils.couch import LockManager, ReleaseOnError


class MultiLockManager(list):
    def __enter__(self):
        return [lock_manager.__enter__() for lock_manager in self]

    def __exit__(self, exc_type, exc_val, exc_tb):
        for lock_manager in self:
            lock_manager.__exit__(exc_type, exc_val, exc_tb)


class FormProcessingResult(object):
    def __init__(self, submitted_form, existing_duplicate=None):
        self.submitted_form = submitted_form
        self.existing_duplicate = existing_duplicate

        if submitted_form.is_duplicate:
            assert existing_duplicate is None

        if existing_duplicate:
            assert existing_duplicate.is_deprecated

        self.interface = FormProcessorInterface(self.submitted_form.domain)

    def _get_form_lock(self, form_id):
        return self.interface.acquire_lock_for_xform(form_id)

    def get_locked_forms(self):
        if self.existing_duplicate:
            # Lock docs with their original ID's (before they got switched during deprecation)
            new_id = self.existing_duplicate.form_id
            old_id = self.existing_duplicate.orig_id
            return MultiLockManager([
                LockManager(self.submitted_form, self._get_form_lock(new_id)),
                LockManager(self.existing_duplicate, self._get_form_lock(old_id)),
            ])
        else:
            return MultiLockManager([
                LockManager(self.submitted_form, self._get_form_lock(self.submitted_form.form_id))
            ])


class LockedFormProcessingResult(FormProcessingResult):
    def __init__(self, submitted_form):
        super(LockedFormProcessingResult, self).__init__(submitted_form)
        assert submitted_form.is_normal
        self.lock = self._get_form_lock(submitted_form.form_id)

    def get_locked_forms(self):
        return MultiLockManager([LockManager(self.submitted_form, self.lock)])


def process_xform_xml(domain, instance, attachments=None):
    """
    Create a new xform to ready to be saved to a database in a thread-safe manner
    Returns a LockManager containing the new XFormInstance(SQL) and its lock,
    or raises an exception if anything goes wrong.

    attachments is a dictionary of the request.FILES that are not the xform;
    key is parameter name, value is django MemoryFile object stream
    """
    attachments = attachments or {}

    try:
        return _create_new_xform(domain, instance, attachments=attachments)
    except XMLSyntaxError as e:
        return _get_submission_error(domain, instance, e)
    except DuplicateError as e:
        return _handle_id_conflict(instance, e.xform, domain)


def _create_new_xform(domain, instance_xml, attachments=None):
    """
    create but do not save an XFormInstance from an xform payload (xml_string)
    optionally set the doc _id to a predefined value (_id)
    return doc _id of the created doc

    `process` is transformation to apply to the form right before saving
    This is to avoid having to save multiple times

    If xml_string is bad xml
      - raise couchforms.XMLSyntaxError
      :param domain:

    """
    from corehq.form_processor.interfaces.processor import FormProcessorInterface
    interface = FormProcessorInterface(domain)

    assert attachments is not None
    form_data = convert_xform_to_json(instance_xml)
    adjust_datetimes(form_data)

    xform = interface.new_xform(form_data)
    xform.domain = domain

    # Maps all attachments to uniform format and adds form.xml to list before storing
    attachments = map(
        lambda a: Attachment(name=a[0], raw_content=a[1], content_type=a[1].content_type),
        attachments.items()
    )
    attachments.append(Attachment(name='form.xml', raw_content=instance_xml, content_type='text/xml'))
    interface.store_attachments(xform, attachments)

    result = LockedFormProcessingResult(xform)
    with ReleaseOnError(result.lock):
        if interface.is_duplicate(xform.form_id):
            raise DuplicateError(xform)

    return result


def _get_submission_error(domain, instance, error):
    """
    Handle's a hard failure from posting a form to couch.
    :returns: xform error instance with raw xml as attachment
    """
    try:
        message = unicode(error)
    except UnicodeDecodeError:
        message = unicode(str(error), encoding='utf-8')

    xform = FormProcessorInterface(domain).submission_error_form_instance(instance, message)
    return FormProcessingResult(xform)


def _handle_id_conflict(instance, xform, domain):
    """
    For id conflicts, we check if the files contain exactly the same content,
    If they do, we just log this as a dupe. If they don't, we deprecate the
    previous form and overwrite it with the new form's contents.
    """

    assert domain
    conflict_id = xform.form_id

    interface = FormProcessorInterface(domain)
    if interface.is_duplicate(conflict_id, domain):
        # It looks like a duplicate/edit in the same domain so pursue that workflow.
        return _handle_duplicate(xform, instance)
    else:
        # the same form was submitted to two domains, or a form was submitted with
        # an ID that belonged to a different doc type. these are likely developers
        # manually testing or broken API users. just resubmit with a generated ID.
        xform = interface.assign_new_id(xform)
        return FormProcessingResult(xform)


def _handle_duplicate(new_doc, instance):
    """
    Handle duplicate xforms and xform editing ('deprecation')

    existing doc *must* be validated as an XFormInstance in the right domain
    and *must* include inline attachments

    """
    interface = FormProcessorInterface(new_doc.domain)
    conflict_id = new_doc.form_id
    existing_doc = FormAccessors(new_doc.domain).get_with_attachments(conflict_id)

    existing_md5 = existing_doc.xml_md5()
    new_md5 = new_doc.xml_md5()

    if existing_md5 != new_md5:
        # if the form contents are not the same:
        #  - "Deprecate" the old form by making a new document with the same contents
        #    but a different ID and a doc_type of XFormDeprecated
        #  - Save the new instance to the previous document to preserve the ID
        existing_doc, new_doc = apply_deprecation(existing_doc, new_doc, interface)

        return FormProcessingResult(new_doc, existing_doc)
    else:
        # follow standard dupe handling, which simply saves a copy of the form
        # but a new doc_id, and a doc_type of XFormDuplicate
        duplicate = interface.deduplicate_xform(new_doc)
        return FormProcessingResult(duplicate)


def apply_deprecation(existing_xform, new_xform, interface=None):
    # if the form contents are not the same:
    #  - "Deprecate" the old form by making a new document with the same contents
    #    but a different ID and a doc_type of XFormDeprecated
    #  - Save the new instance to the previous document to preserve the ID

    interface = interface or FormProcessorInterface(existing_xform.domain)

    new_xform.form_id = existing_xform.form_id
    existing_xform = interface.assign_new_id(existing_xform)
    existing_xform.orig_id = new_xform.form_id

    # and give the new doc server data of the old one and some metadata
    new_xform.received_on = existing_xform.received_on
    new_xform.deprecated_form_id = existing_xform.form_id
    new_xform.edited_on = datetime.datetime.utcnow()
    existing_xform.edited_on = new_xform.edited_on

    return interface.apply_deprecation(existing_xform, new_xform)
