import os
import uuid

from django.core.management.base import BaseCommand

import magic

from corehq.blobs import CODES, get_blob_db
from corehq.util.view_utils import reverse


class Command(BaseCommand):
    help = "Upload a file to blob storage for subsequent download"

    def add_arguments(self, parser):
        parser.add_argument('file_path')
        parser.add_argument('--keep-hours', type=int, default=24,
                            help="Number of hours to store file. Defaults to 24.")

    def handle(self, file_path, keep_hours, **options):
        unique_id = str(uuid.uuid4())
        name = os.path.basename(file_path)
        mime_type = magic.from_file(file_path, mime=True)

        with open(file_path, 'rb') as file_obj:
            get_blob_db().put(
                file_obj,
                domain=unique_id,
                parent_id=unique_id,
                type_code=CODES.tempfile,
                key=unique_id,
                name=name,
                content_type=mime_type,
                timeout=keep_hours * 60,
            )

        print(f"{name} has been saved to blob storage for {keep_hours} hours. Download it here:")
        print(reverse('download_blob', params={'key': unique_id}, absolute=True))
