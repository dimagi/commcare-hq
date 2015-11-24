import hashlib

from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import Attachment
from corehq.form_processor.utils import convert_xform_to_json, adjust_datetimes
from couchforms import XMLSyntaxError
from couchforms.exceptions import SubmissionError, DuplicateError
from dimagi.utils.couch import LockManager, ReleaseOnError


class MultiLockManager(list):
    def __enter__(self):
        return [lock_manager.__enter__() for lock_manager in self]

    def __exit__(self, exc_type, exc_val, exc_tb):
        for lock_manager in self:
            lock_manager.__exit__(exc_type, exc_val, exc_tb)


def process_xform(domain, instance, attachments=None, process=None):
    """
    Create a new xform to ready to be saved to couchdb in a thread-safe manner
    Returns a LockManager containing the new XFormInstance and its lock,
    or raises an exception if anything goes wrong.

    attachments is a dictionary of the request.FILES that are not the xform;
    key is parameter name, value is django MemoryFile object stream

    """
    attachments = attachments or {}

    try:
        xform_lock = _create_new_xform(domain, instance, attachments=attachments, process=process)
    except XMLSyntaxError as e:
        xform = _log_hard_failure(domain, instance, process, e)
        raise SubmissionError(xform)
    except DuplicateError as e:
        return _handle_id_conflict(instance, e.xform, domain)
    return MultiLockManager([xform_lock])


def _create_new_xform(domain, instance_xml, attachments=None, process=None):
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

    # Maps all attachments to uniform format and adds form.xml to list before storing
    attachments = map(
        lambda a: Attachment(name=a[0], raw_content=a[1], content_type=a[1].content_type),
        attachments.items()
    )
    attachments.append(Attachment(name='form.xml', raw_content=instance_xml, content_type='text/xml'))
    interface.store_attachments(xform, attachments)

    # this had better not fail, don't think it ever has
    # if it does, nothing's saved and we get a 500
    if process:
        process(xform)

    lock = interface.acquire_lock_for_xform(xform.form_id)
    with ReleaseOnError(lock):
        if interface.is_duplicate(xform.form_id):
            raise DuplicateError(xform)

    return LockManager(xform, lock)


def _log_hard_failure(domain, instance, process, error):
    """
    Handle's a hard failure from posting a form to couch.

    Currently, it will save the raw payload to couch in a hard-failure doc
    and return that doc.
    """
    try:
        message = unicode(error)
    except UnicodeDecodeError:
        message = unicode(str(error), encoding='utf-8')

    return FormProcessorInterface(domain).log_submission_error(instance, message, process)


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
        lock = interface.acquire_lock_for_xform(xform.form_id)
        return MultiLockManager([LockManager(xform, lock)])


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
    new_md5 = hashlib.md5(instance).hexdigest()

    if existing_md5 != new_md5:
        # if the form contents are not the same:
        #  - "Deprecate" the old form by making a new document with the same contents
        #    but a different ID and a doc_type of XFormDeprecated
        #  - Save the new instance to the previous document to preserve the ID
        existing_doc, new_doc = interface.deprecate_xform(existing_doc, new_doc)

        # Lock docs with their original ID's (before they got switched during deprecation)
        return MultiLockManager([
            LockManager(new_doc, interface.acquire_lock_for_xform(existing_doc.form_id)),
            LockManager(existing_doc, interface.acquire_lock_for_xform(existing_doc.orig_id)),
        ])
    else:
        # follow standard dupe handling, which simply saves a copy of the form
        # but a new doc_id, and a doc_type of XFormDuplicate
        duplicate = interface.deduplicate_xform(new_doc)
        return MultiLockManager([
            LockManager(duplicate, interface.acquire_lock_for_xform(duplicate.form_id)),
        ])
