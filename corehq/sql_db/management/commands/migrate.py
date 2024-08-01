from django.core.management.base import no_translations
from django.core.management.commands import migrate

from corehq.preindex import django_migrations as reindexer


class Command(migrate.Command):

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--no-reindex',
            action='store_false', dest='should_reindex', default=True,
            help='Skip Couch reindex operations, even if migrations ask for them.')
        # NOTE: This is only enforced by migrate.py. If this command is called through code,
        # this parameter will have no effect
        parser.add_argument(
            '--skip-gevent', action='store_true', default=False, help='when true, avoids monkey patching gevent')

    @no_translations
    def handle(self, *args, should_reindex, **options):
        result = super().handle(*args, **options)

        if reindexer.should_reindex and should_reindex:
            reindexer.run_reindex()

        return result
