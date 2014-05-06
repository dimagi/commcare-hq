from custom.uth.utils import create_case, match_case, attach_images_to_case
from custom.uth.models import SonositeUpload, VscanUpload
from celery.task import task
import io


@task
def async_create_case(upload_id):
    upload_doc = SonositeUpload.get(upload_id)

    files = {}
    for f in upload_doc._attachments.keys():
        files[f] = io.BytesIO(upload_doc.fetch_attachment(f))

    create_case(upload_doc.related_case_id, files)

    # TODO delete doc if processing is successful


@task
def async_find_and_attach(upload_id):
    upload_doc = VscanUpload.get(upload_id)

    case = match_case(
        upload_doc.scanner_serial,
        upload_doc.scan_id,
        upload_doc.date
    )

    attach_images_to_case(case, [])

    # TODO delete doc if successful
