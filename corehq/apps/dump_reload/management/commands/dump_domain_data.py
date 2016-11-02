import gzip
import os
import zipfile
from collections import Counter
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.dump_reload.const import DATETIME_FORMAT
from corehq.apps.dump_reload.couch import CouchDataDumper
from corehq.apps.dump_reload.sql import SqlDataDumper


class Command(BaseCommand):
    help = "Dump a domain's data to disk."
    args = '<domain>'

    def add_arguments(self, parser):
        parser.add_argument('-e', '--exclude', dest='exclude', action='append', default=[],
            help='An app_label or app_label.ModelName to exclude '
                 '(use multiple --exclude to exclude multiple apps/models).')
        parser.add_argument('--console', action='store_true', default=False, dest='console',
                            help = 'Write output to the console instead of to file.')

    def handle(self, domain, **options):
        excludes = options.get('exclude')
        console = options.get('console')
        show_traceback = options.get('traceback')

        utcnow = datetime.utcnow().strftime(DATETIME_FORMAT)
        zipname = 'data-dump-{}-{}.zip'.format(domain, utcnow)
        self.stdout.ending = None
        stats = Counter()
        dumpers = [SqlDataDumper, CouchDataDumper]

        for dumper in dumpers:
            filename = _get_dump_stream_filename(dumper.slug, domain, utcnow)
            stream = self.stdout if console else gzip.open(filename, 'wb')
            try:
                stats += dumper(domain, excludes).dump(stream)
            except Exception as e:
                if show_traceback:
                    raise
                raise CommandError("Unable to serialize database: %s" % e)
            finally:
                if stream:
                    stream.close()

            if not console:
                with zipfile.ZipFile(zipname, 'a') as z:
                    z.write(filename, '{}.gz'.format(dumper.slug))

                os.remove(filename)

        print '{0} Dump Stats {0}'.format('-' * 32)
        for model in sorted(stats):
            print "{:<40}: {}".format(model, stats[model])
        print '{0}{0}'.format('-' * 38)
        print 'Dumped {} objects'.format(sum(stats.values()))
        print '{0}{0}'.format('-' * 38)

        print '\nData dumped to file: {}'.format(zipname)


def _get_dump_stream_filename(slug, domain, utcnow):
    return 'dump-{}-{}-{}.gz'.format(slug, domain, utcnow)
