from custom.uth.utils import create_case
from custom.uth.models import SonositeUpload
from celery.task import task
import io
import zipfile


@task
def async_create_case(upload_id):
    upload_doc = SonositeUpload.get(upload_id)
    zip_file = zipfile.ZipFile(
        io.BytesIO(
            upload_doc.fetch_attachment('upload.zip')
        )
    )

    create_case(upload_doc.case_id, zip_file)

    # TODO delete case if processing is successful
