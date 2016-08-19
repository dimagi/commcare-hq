from corehq.blobs.mixin import BlobMixin
from custom.uth.utils import create_case, match_case, attach_images_to_case, submit_error_case
from custom.uth.models import SonositeUpload, VscanUpload
from celery.task import task
import io


def get_files_from_doc(doc):
    """
    Load all attachments from a couch doc into a readable object
    """

    files = {}
    attachments = doc.blobs if isinstance(doc, BlobMixin) else doc._attachments
    for f in attachments:
        if f[-4:].lower() != '.xml':
            # we really only want images/videos, but specifically
            # blacklisting uploaded config files
            files[f] = io.BytesIO(doc.fetch_attachment(f))

    return files


@task(ignore_result=True)
def async_create_case(upload_id):
    """
    Task backend for sonosite upload
    """

    upload_doc = SonositeUpload.get(upload_id)
    files = get_files_from_doc(upload_doc)
    create_case(upload_doc.related_case_id, files)

    upload_doc.delete()


@task(ignore_result=True)
def async_find_and_attach(upload_id):
    """
    Task backend for Vscan upload
    """

    case = None

    try:
        upload_doc = VscanUpload.get(upload_id)
        files = get_files_from_doc(upload_doc)
        case = match_case(
            upload_doc.scanner_serial,
            upload_doc.scan_id,
        )

        if case:
            files = {}
            attachments = (upload_doc.blobs
                if isinstance(upload_doc, BlobMixin)
                else upload_doc._attachments)
            for f in attachments:
                files[f] = io.BytesIO(upload_doc.fetch_attachment(f))

            attach_images_to_case(case._id, files)
        else:
            return -1

        upload_doc.delete()
    except:
        # mark the case as having errored (if we know what it is)
        # but reraise the error since we don't want to hide it
        if case:
            submit_error_case(case._id)

        raise
