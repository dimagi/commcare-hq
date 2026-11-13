import shutil
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from couchdbkit import ResourceNotFound

from corehq.apps.export.dbaccessors import get_export_instance_in_domain
from corehq.util.files import safe_filename


def download_saved_export(domain, export_id, dest_dir=None):
    # Downloads the latest saved export to shared-directory
    dest_dir = (dest_dir or settings.SHARED_DRIVE_ROOT).rstrip()
    export_instance = get_export_instance_in_domain(domain, export_id)
    export_archive_path = '{}/{}_{}.zip'.format(
        dest_dir,
        safe_filename(export_instance.name.encode('ascii', 'replace') or 'Export'),
        datetime.utcnow().isoformat()
    )
    payload = export_instance.get_payload(stream=True)
    print("Downloading Export to {}".format(export_archive_path))
    with open(export_archive_path, 'wb') as download:
        shutil.copyfileobj(payload, download)
    print("Download Finished!")


class Command(BaseCommand):
    # useful if the export sizes are too big to succeed via regular UI download
    help = "Download saved exports to a directory"

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            help="Domain the export belongs to",
        )
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

    def handle(self, domain, export_id, **options):
        dest_dir = options.pop('destination_dir')
        try:
            download_saved_export(domain, export_id, dest_dir=dest_dir)
        except ResourceNotFound:
            raise CommandError(f"Export {export_id} not found in domain {domain}")
