from custom.uth.utils import create_case, match_case, attach_images_to_case
from custom.uth.models import SonositeUpload, VscanUpload
from celery.task import task
import io


def get_files_from_doc(doc):
    files = {}
    for f in doc._attachments.keys():
        files[f] = io.BytesIO(doc.fetch_attachment(f))

    return files


@task
def async_create_case(upload_id):
    upload_doc = SonositeUpload.get(upload_id)
    files = get_files_from_doc(upload_doc)
    create_case(upload_doc.related_case_id, files)

    # TODO delete doc if processing is successful


@task
def async_find_and_attach(upload_id):
    upload_doc = VscanUpload.get(upload_id)
    files = get_files_from_doc(upload_doc)
    case = match_case(
        upload_doc.scanner_serial,
        upload_doc.scan_id,
        upload_doc.date
    )

    if case:
        files = {}
        for f in upload_doc._attachments.keys():
            files[f] = io.BytesIO(upload_doc.fetch_attachment(f))

        attach_images_to_case(case._id, files)
    else:
        return -1

    # TODO delete doc if successful
