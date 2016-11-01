import gzip

from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.dump_reload.sql import dump_sql_data
from corehq.util.decorators import ContextDecorator

SQL_FILE_PREFIX = 'dump-sql'
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
        try:
            self.stdout.ending = None
            stream = self.stdout if console else _get_dump_stream(domain, utcnow)
            try:
                with allow_form_processing_queries():
                    dump_sql_data(domain, excludes, stream)
            finally:
                if stream:
                    stream.close()
        except Exception as e:
            if show_traceback:
                raise
            raise CommandError("Unable to serialize database: %s" % e)


def _get_dump_stream(domain, utcnow):
    filename = '{}-{}-{}.gz'.format(SQL_FILE_PREFIX, domain, utcnow)
    return gzip.open(filename, 'wb')


class allow_form_processing_queries(ContextDecorator):
    def __enter__(self):
        from django.conf import UserSettingsHolder
        override = UserSettingsHolder(settings._wrapped)
        setattr(override, 'ALLOW_FORM_PROCESSING_QUERIES', True)
        self.wrapped = settings._wrapped
        settings._wrapped = override

    def __exit__(self, exc_type, exc_val, exc_tb):
        settings._wrapped = self.wrapped
        del self.wrapped
