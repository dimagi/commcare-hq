from optparse import make_option

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    args = ''
    help = "Call 'migrate' for each configured database"

    option_list = BaseCommand.option_list + (
        make_option(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False),
        )

    def handle(self, *args, **options):
        for db_alias in settings.DATABASES.keys():
            print '\n======================= Migrating DB: {} ======================='.format(db_alias)
            call_command('migrate', database=db_alias, noinput=options['noinput'])
