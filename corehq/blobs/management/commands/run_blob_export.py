from __future__ import absolute_import
from __future__ import unicode_literals
import logging
import os
import sys
from django.core.management import BaseCommand, CommandError
from corehq.blobs.migrate import EXPORTERS
from corehq.blobs.zipdb import get_export_filename
from corehq.util.decorators import change_log_level


USAGE = """Usage: ./manage.py run_blob_export [options] <slug> <domain>

Slugs:

{}

""".format('\n'.join(sorted(EXPORTERS)))


class Command(BaseCommand):
    """
    Example: ./manage.py run_blob_export [options] domain

    Dump XForms in parallel:
        ./manage.py run_blob_export -e sql_xforms --limit-to-db p0 domain
         ...
        ./manage.py run_blob_export -e sql_xforms --limit-to-db pN domain
    """
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('-e', '--exporter', dest='exporters', action='append', default=[],
                            help='Exporter slug to run '
                                 '(use multiple --slug to run multiple exporters or --all to run them all).')
        parser.add_argument('--all', action='store_true', default=False,
                            help='Run all exporters')
        parser.add_argument('--chunk-size', type=int, default=100,
                            help='Maximum number of records to read from couch at once.')
        parser.add_argument('--limit-to-db', dest='limit_to_db',
                            help="When specifying a SQL importer use this to restrict "
                                 "the exporter to a single database.")

    @change_log_level('boto3', logging.WARNING)
    @change_log_level('botocore', logging.WARNING)
    def handle(self, domain=None, reset=False,
               chunk_size=100, all=None, limit_to_db=None, **options):
        exporters = options.get('exporters')

        if not domain:
            raise CommandError(USAGE)

        if all:
            exporters = list(EXPORTERS)

        migrator_options = {}
        if limit_to_db:
            migrator_options['limit_to_db'] = limit_to_db

        for exporter_slug in exporters:
            try:
                exporter = EXPORTERS[exporter_slug]
            except KeyError:
                raise CommandError(USAGE)

            self.stdout.write("\nRunning exporter: {}\n{}".format(exporter_slug, '-' * 50))
            export_filename = get_export_filename(exporter_slug, domain)
            if os.path.exists(export_filename):
                reset_export = False
                self.stderr.write(
                    "WARNING: export file for {} exists. "
                    "Resuming export progress. Delete file to reset progress.".format(exporter_slug)
                )
            else:
                reset_export = True  # always reset if the file doesn't already exist
            exporter.by_domain(domain)
            total, skips = exporter.migrate(reset=reset_export, chunk_size=chunk_size, **migrator_options)
            if skips:
                sys.exit(skips)
