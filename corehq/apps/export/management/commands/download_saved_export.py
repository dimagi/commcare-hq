from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import shutil
from datetime import datetime
from django.conf import settings
from django.core.management.base import BaseCommand

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.util.files import safe_filename


def download_saved_export(export_id, dest_dir=None):
    # Downloads the latest saved export to shared-directory
    dest_dir = (dest_dir or settings.SHARED_DRIVE_ROOT).rstrip()
    export_instance = get_properly_wrapped_export_instance(export_id)
    export_archive_path = '{}/{}_{}.zip'.format(
        dest_dir,
        safe_filename(export_instance.name.encode('ascii', 'replace') or 'Export'),
        datetime.utcnow().isoformat()
    )
    payload = export_instance.get_payload(stream=True)
    print("Downloading Export to {}".format(export_archive_path))
    with open(export_archive_path, 'w') as download:
        shutil.copyfileobj(payload, download)
    print("Download Finished!")


class Command(BaseCommand):
    # useful if the export sizes are too big to succeed via regular UI download
    help = "Download saved exports to a directory"

    def add_arguments(self, parser):

        parser.add_argument(
            'export_id',
            help="Export ID of the saved export"
        )
        parser.add_argument(
            '--dest-dir',
            dest='destination_dir',
            default=settings.SHARED_DRIVE_ROOT,
            help='Destination directory',
        )

    def handle(self, export_id, **options):
        dest_dir = options.pop('destination_dir')
        download_saved_export(export_id, dest_dir=dest_dir)
