import gzip
from collections import Counter
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.dump_reload.couch import CouchDataDumper
from corehq.apps.dump_reload.sql import SqlDataDumper

DATETIME_FORMAT = '%Y-%m-%dT%H%M%SZ'


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
        self.stdout.ending = None
        stats = Counter()
        dumpers = [SqlDataDumper, CouchDataDumper]
        for dumper in dumpers:
            stream = self.stdout if console else _get_dump_stream(dumper.slug, domain, utcnow)
            try:
                stats += dumper(domain, excludes).dump(stream)
            except Exception as e:
                if show_traceback:
                    raise
                raise CommandError("Unable to serialize database: %s" % e)
            finally:
                if stream:
                    stream.close()

        for model in sorted(stats):
            print "{:<40}: {}".format(model, stats[model])


def _get_dump_stream(slug, domain, utcnow):
    filename = 'dump-{}-{}-{}.gz'.format(slug, domain, utcnow)
    return gzip.open(filename, 'wb')
