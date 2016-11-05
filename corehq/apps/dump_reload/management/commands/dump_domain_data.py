import gzip
import json
import os
import zipfile
from collections import Counter
from datetime import datetime

from couchdbkit.exceptions import ResourceNotFound
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.domain.models import Domain
from corehq.apps.dump_reload.const import DATETIME_FORMAT
from corehq.apps.dump_reload.couch import CouchDataDumper
from corehq.apps.dump_reload.couch.dump import ToggleDumper
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

    def handle(self, domain_name, **options):
        excludes = options.get('exclude')
        console = options.get('console')
        show_traceback = options.get('traceback')

        try:
            domain = Domain.get_by_name(domain_name)
        except ResourceNotFound:
            raise CommandError("Domain not found: {}".format(domain_name))

        utcnow = datetime.utcnow().strftime(DATETIME_FORMAT)
        zipname = 'data-dump-{}-{}.zip'.format(domain_name, utcnow)

        self.stdout.write("Dumping domain object")
        with zipfile.ZipFile(zipname, 'a') as z:
            z.writestr("domain.json", json.dumps(domain.to_json()))

        self.stdout.ending = None
        stats = Counter()
        dumpers = [SqlDataDumper, CouchDataDumper, ToggleDumper]

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
                with zipfile.ZipFile(zipname, 'a') as z:
                    z.write(filename, '{}.gz'.format(dumper.slug))

                os.remove(filename)

        self.stdout.write('{0} Dump Stats {0}'.format('-' * 32))
        for model in sorted(stats):
            self.stdout.write("{:<40}: {}".format(model, stats[model]))
        self.stdout.write('{0}{0}'.format('-' * 38))
        self.stdout.write('Dumped {} objects'.format(sum(stats.values())))
        self.stdout.write('{0}{0}'.format('-' * 38))

        self.stdout.write('\nData dumped to file: {}'.format(zipname))


def _get_dump_stream_filename(slug, domain, utcnow):
    return 'dump-{}-{}-{}.gz'.format(slug, domain, utcnow)
