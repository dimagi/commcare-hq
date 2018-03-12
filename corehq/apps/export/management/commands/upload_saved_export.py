from __future__ import absolute_import
from __future__ import unicode_literals
import os

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.apps.export.export import save_export_payload


class Command(BaseCommand):
    help = "Upload saved export"

    def add_arguments(self, parser):

        parser.add_argument(
            'export_id',
            help="Export ID of the saved export"
        )
        parser.add_argument(
            'path',
            help='Path to export archive',
        )

    def handle(self, export_id, **options):
        path = options.pop('path')
        if not os.path.isfile(path):
            raise CommandError("File not found: {}".format(path))

        export_instance = get_properly_wrapped_export_instance(export_id)
        with open(path, 'rb') as payload:
            save_export_payload(export_instance, payload)
