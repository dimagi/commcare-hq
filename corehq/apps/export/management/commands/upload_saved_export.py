import os

from django.core.management.base import BaseCommand, CommandError

from couchdbkit import ResourceNotFound

from corehq.apps.export.dbaccessors import get_export_instance_in_domain
from corehq.apps.export.export import save_export_payload


class Command(BaseCommand):
    help = "Upload saved export"

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
            'path',
            help='Path to export archive',
        )

    def handle(self, domain, export_id, **options):
        path = options.pop('path')
        if not os.path.isfile(path):
            raise CommandError("File not found: {}".format(path))

        try:
            export_instance = get_export_instance_in_domain(domain, export_id)
        except ResourceNotFound:
            raise CommandError(f"Export {export_id} not found in domain {domain}")
        with open(path, 'rb') as payload:
            save_export_payload(export_instance, payload)
