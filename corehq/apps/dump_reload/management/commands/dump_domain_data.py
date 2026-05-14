from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.dump_reload.archive import (
    SimpleSingleStreamWriter,
    ZippedGzipArchiveWriter,
)
from corehq.apps.dump_reload.const import DATETIME_FORMAT
from corehq.apps.dump_reload.couch import CouchDataDumper
from corehq.apps.dump_reload.couch.dump import DomainDumper, ToggleDumper
from corehq.apps.dump_reload.sql import SqlDataDumper

# Domain dumper should be first since it validates that the domain exists.
DUMPERS = [DomainDumper, SqlDataDumper, CouchDataDumper, ToggleDumper]


class Command(BaseCommand):
    # This doesn't include SyncLog data
    help = "Dump a domain's data to disk."

    def add_arguments(self, parser):
        parser.add_argument('domain_name')
        parser.add_argument(
            '-e', '--exclude', dest='exclude', action='append', default=[],
            help='An app_label, app_label.ModelName or CouchDB doc_type to exclude '
                 '(use multiple --exclude to exclude multiple apps/models).'
        )
        parser.add_argument(
            '-i', '--include', dest='include', action='append', default=[],
            help='An app_label, app_label.ModelName or CouchDB doc_type to include '
                 '(use multiple --include to include multiple apps/models).'
        )
        parser.add_argument(
            '--console', action='store_true', default=False, dest='console',
            help='Write output to the console instead of to file.'
        )
        parser.add_argument('--dumper', dest='dumpers', action='append', default=[],
                            help='Dumper slug to run (use multiple --dumper to run multiple dumpers).')

    def handle(self, domain_name, **options):
        excludes = options.get('exclude')
        includes = options.get('include')
        console = options.get('console')
        show_traceback = options.get('traceback')
        requested_dumpers = options.get('dumpers')

        utcnow = datetime.utcnow().strftime(DATETIME_FORMAT)
        self.stdout.ending = None

        dumpers = [d for d in DUMPERS if not requested_dumpers or d.slug in requested_dumpers]
        if console:
            archive = SimpleSingleStreamWriter(self.stdout)
        else:
            archive = ZippedGzipArchiveWriter(f"data-dump-{domain_name}-{utcnow}.zip")

        with archive:
            for dumper in dumpers:
                try:
                    with archive.open_stream(dumper.slug) as stream:
                        stream.meta = dumper(domain_name, excludes, includes).dump(stream)
                except Exception as e:
                    if show_traceback:
                        raise
                    raise CommandError(f"Unable to serialize database: {e}")

        self._print_stats(archive.meta)
        if archive.path:
            self.stdout.write(f'\nData dumped to file: {archive.path}')

    def _print_stats(self, meta):
        self.stdout.ending = '\n'
        self.stdout.write('{0} Dump Stats {0}'.format('-' * 32))
        for dumper, models in sorted(meta.items()):
            self.stdout.write(dumper)
            for model, count in sorted(models.items()):
                self.stdout.write("  {:<50}: {}".format(model, count))
        self.stdout.write('{0}{0}'.format('-' * 38))
        self.stdout.write('Dumped {} objects'.format(sum(
            count for model in meta.values() for count in model.values()
        )))
        self.stdout.write('{0}{0}'.format('-' * 38))
