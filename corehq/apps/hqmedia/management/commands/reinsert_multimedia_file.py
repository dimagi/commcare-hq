from django.core.management.base import BaseCommand
from corehq.apps.domain import SHARED_DOMAIN

from corehq.apps.hqmedia.models import CommCareImage
from corehq.blobs.exceptions import NotFound
from corehq.blobs import CODES, get_blob_db


class Command(BaseCommand):
    help = "Reinserts a multimedia file into the blob db with a reference if it was deleted"
    # Error message this should fix when building an application zip:
    # CommCareImage 51e4051a7ae3358a041a0f83170031dd attachment: '3699549047a1e9a769d58bb88946b5fd-800x600.JPEG'

    def add_arguments(self, parser):
        parser.add_argument(
            "--image_id", help="CommCareImage id to update", required=True,
        )
        parser.add_argument(
            "--attachment_id",
            help="Blob attachment id. Of the form uuid-heightxwidth.JPEG",
            required=True,
        )
        parser.add_argument(
            "--filename", help="Path to file to insert", required=True,
        )

    def handle(self, **options):
        db = get_blob_db()

        image = CommCareImage.get(options["image_id"])
        with open(options["filename"], "rb") as f:
            image_data = f.read()
        blob_key = image.external_blobs[options["attachment_id"]].key

        try:
            db.get(blob_key, CODES.multimedia)
            raise Exception("This blob already exists. You cannot overwrite it this way.")
        except NotFound:
            pass

        image.put_attachment(
            image_data,
            image.attachment_id,
            content_type=image.get_mime_type(image_data, filename=options["attachment_id"]),
            domain=SHARED_DOMAIN,
        )

        print(f"Successfully updated image {options['attachment_id']}")
