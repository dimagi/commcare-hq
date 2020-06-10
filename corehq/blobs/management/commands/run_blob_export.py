import logging
import os
import sys
from django.core.management import BaseCommand, CommandError
from corehq.blobs.export import EXPORTERS
from corehq.blobs.targzipdb import get_export_filename
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
        parser.add_argument('--extend', dest='extends', action='append', default=[],
                            help='Extend a previous export file. '
                                 'You can extend multiple files.')

    @change_log_level('boto3', logging.WARNING)
    @change_log_level('botocore', logging.WARNING)
    def handle(self, domain=None, reset=False,
               chunk_size=100, all=None, limit_to_db=None, **options):
        exporters = options.get('exporters')
        extends = options.get('extends')

        if not domain:
            raise CommandError(USAGE)

        if all:
            exporters = list(EXPORTERS)

        for exporter_slug in exporters:
            try:
                exporter_cls = EXPORTERS[exporter_slug]
            except KeyError:
                raise CommandError(USAGE)

            self.stdout.write("\nRunning exporter: {}\n{}".format(exporter_slug, '-' * 50))
            export_filename = get_export_filename(exporter_slug, domain)
            if os.path.exists(export_filename):
                raise CommandError(f"Export file '{export_filename}' exists. "
                                   f"Remove the file and re-run the command.")

            exporter = exporter_cls(domain)
            total, skips = exporter.migrate(
                export_filename,
                chunk_size=chunk_size,
                limit_to_db=limit_to_db,
                extends=extends,
            )
            if skips:
                sys.exit(skips)
