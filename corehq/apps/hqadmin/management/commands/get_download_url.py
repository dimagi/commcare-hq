import os

from django.core.management.base import BaseCommand

import magic

from corehq.apps.hqadmin.utils import get_download_url


class Command(BaseCommand):
    help = "Upload a file to blob storage for subsequent download"

    def add_arguments(self, parser):
        parser.add_argument('file_path')
        parser.add_argument('--keep-hours', type=int, default=24,
                            help="Number of hours to store file. Defaults to 24.")

    def handle(self, file_path, keep_hours, **options):
        name = os.path.basename(file_path)
        mime_type = magic.from_file(file_path, mime=True)
        with open(file_path, 'rb') as file_obj:
            download_url = get_download_url(file_obj, name, mime_type, keep_hours * 60)

        print(f"'{name}' has been saved to blob storage for {keep_hours} hours. Download it here:")
        print(download_url)
