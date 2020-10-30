import datetime
import logging
import os
import sys

from django.core.management import BaseCommand, CommandError

from corehq.blobs.export import EXPORTERS
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

    To top-up an older blob dump, first extract a list of names from the archive:
        $ tar --list -f blob_export.tar.gz > blob_export.list
    Then provide this file to the `--already_exported` argument to skip over
    those objects in this dump.
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
        parser.add_argument('--already_exported', dest='already_exported',
                            help='Pass a file with a list of blob names already exported')

    @change_log_level('boto3', logging.WARNING)
    @change_log_level('botocore', logging.WARNING)
    def handle(self, domain=None, reset=False,
               chunk_size=100, all=None, limit_to_db=None, **options):
        exporters = options.get('exporters')
        already_exported = _get_names_from_file(options['already_exported'])

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
            export_filename = _get_export_filename(exporter_slug, domain, already_exported)
            if os.path.exists(export_filename):
                raise CommandError(f"Export file '{export_filename}' exists. "
                                   f"Remove the file and re-run the command.")

            exporter = exporter_cls(domain)
            total, skips = exporter.migrate(
                export_filename,
                chunk_size=chunk_size,
                limit_to_db=limit_to_db,
                already_exported=already_exported,
            )
            if skips:
                sys.exit(skips)


def _get_names_from_file(filename):
    if not filename:
        return set()
    with open(filename) as f:
        names = {line.strip() for line in f}
    print("Found {} existing blobs, these will be skipped".format(len(names)))
    return names


def _get_export_filename(slug, domain, already_exported):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H.%M')
    part = '-part' if already_exported else ''
    return f'{timestamp}-{domain}-{slug}{part}.tar.gz'
