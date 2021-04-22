import gzip
import json
import os
import zipfile
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.dump_reload.const import DATETIME_FORMAT
from corehq.apps.dump_reload.couch import CouchDataDumper
from corehq.apps.dump_reload.couch.dump import DomainDumper, ToggleDumper
from corehq.apps.dump_reload.sql import SqlDataDumper


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

        self.utcnow = datetime.utcnow().strftime(DATETIME_FORMAT)
        zipname = 'data-dump-{}-{}.zip'.format(domain_name, self.utcnow)

        self.stdout.ending = None
        meta = {}  # {dumper_slug: {model_name: count}}
        # domain dumper should be first since it validates domain exists
        for dumper in [DomainDumper, SqlDataDumper, CouchDataDumper, ToggleDumper]:
            if requested_dumpers and dumper.slug not in requested_dumpers:
                continue

            filename = _get_dump_stream_filename(dumper.slug, domain_name, self.utcnow)
            stream = self.stdout if console else gzip.open(filename, 'wt')
            try:
                meta[dumper.slug] = dumper(domain_name, excludes, includes).dump(stream)
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

        if not console:
            with zipfile.ZipFile(zipname, mode='a', allowZip64=True) as z:
                z.writestr('meta.json', json.dumps(meta, indent=4))

        self._print_stats(meta)
        self.stdout.write('\nData dumped to file: {}'.format(zipname))

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


def _get_dump_stream_filename(slug, domain, utcnow):
    return 'dump-{}-{}-{}.gz'.format(slug, domain, utcnow)
