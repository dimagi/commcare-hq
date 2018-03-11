from __future__ import absolute_import
import gzip
import os
import zipfile
from collections import Counter
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.dump_reload.const import DATETIME_FORMAT
from corehq.apps.dump_reload.couch import CouchDataDumper
from corehq.apps.dump_reload.couch.dump import ToggleDumper, DomainDumper
from corehq.apps.dump_reload.sql import SqlDataDumper


class Command(BaseCommand):
    # This doesn't include SyncLog data
    help = "Dump a domain's data to disk."

    def add_arguments(self, parser):
        parser.add_argument('domain_name')
        parser.add_argument(
            '-e', '--exclude', dest='exclude', action='append', default=[],
            help='An app_label or app_label.ModelName to exclude '
                 '(use multiple --exclude to exclude multiple apps/models).'
        )
        parser.add_argument(
            '--console', action='store_true', default=False, dest='console',
            help='Write output to the console instead of to file.'
        )
        parser.add_argument('--dumper', dest='dumpers', action='append', default=[],
                            help='Dumper slug to run (use multiple --dumper to run multiple dumpers).')

    def handle(self, domain_name, **options):
        excludes = options.get('exclude')
        console = options.get('console')
        show_traceback = options.get('traceback')

        utcnow = datetime.utcnow().strftime(DATETIME_FORMAT)
        zipname = 'data-dump-{}-{}.zip'.format(domain_name, utcnow)

        self.stdout.ending = None
        stats = Counter()
        # domain dumper should be first since it validates domain exists
        dumpers = [DomainDumper, SqlDataDumper, CouchDataDumper, ToggleDumper]

        requested_dumpers = options.get('dumpers')
        if requested_dumpers:
            dumpers = [dumper for dumper in dumpers if dumper.slug in requested_dumpers]

        for dumper in dumpers:
            filename = _get_dump_stream_filename(dumper.slug, domain_name, utcnow)
            stream = self.stdout if console else gzip.open(filename, 'wb')
            try:
                stats += dumper(domain_name, excludes).dump(stream)
            except Exception as e:
                if show_traceback:
                    raise
                raise CommandError("Unable to serialize database: %s" % e)
            finally:
                if stream:
                    stream.close()

            if not console:
                with zipfile.ZipFile(zipname, mode='a', allowZip64=True) as z:
                    z.write(filename, '{}.gz'.format(dumper.slug))

                os.remove(filename)

        self.stdout.ending = '\n'
        self.stdout.write('{0} Dump Stats {0}'.format('-' * 32))
        for model in sorted(stats):
            self.stdout.write("{:<50}: {}".format(model, stats[model]))
        self.stdout.write('{0}{0}'.format('-' * 38))
        self.stdout.write('Dumped {} objects'.format(sum(stats.values())))
        self.stdout.write('{0}{0}'.format('-' * 38))

        self.stdout.write('\nData dumped to file: {}'.format(zipname))


def _get_dump_stream_filename(slug, domain, utcnow):
    return 'dump-{}-{}-{}.gz'.format(slug, domain, utcnow)
