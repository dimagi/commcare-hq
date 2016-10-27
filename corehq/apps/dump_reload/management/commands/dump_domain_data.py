from django.core.management.base import BaseCommand, CommandError

from corehq.apps.dump_reload.sql.dump import dump_sql_data


class Command(BaseCommand):
    help = "Dump a domain's data to disk."
    args = '<domain>'

    def add_arguments(self, parser):
        parser.add_argument('-e', '--exclude', dest='exclude', action='append', default=[],
            help='An app_label or app_label.ModelName to exclude '
                 '(use multiple --exclude to exclude multiple apps/models).')
        parser.add_argument('-o', '--output', default=None, dest='output',
            help='Specifies file to which the output is written.')

    def handle(self, domain, **options):
        excludes = options.get('exclude')
        output = options.get('output')
        show_traceback = options.get('traceback')


        try:
            self.stdout.ending = None
            stream = open(output, 'w') if output else self.stdout
            try:
                dump_sql_data(domain, excludes, stream)
            finally:
                if stream:
                    stream.close()
        except Exception as e:
            if show_traceback:
                raise
            raise CommandError("Unable to serialize database: %s" % e)
