import sys
import gevent
from optparse import make_option

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    args = ''
    help = "Call 'migrate' for each configured database"

    option_list = BaseCommand.option_list + (
        make_option('--noinput', action='store_false', dest='interactive', default=True,
            help='Tells Django to NOT prompt the user for input of any kind.'),
        make_option('--fake', action='store_true', dest='fake', default=False,
            help='Mark migrations as run without actually running them'),
        make_option('--list', '-l', action='store_true', dest='list', default=False,
            help='Show a list of all known migrations and which are applied'),
    )

    def handle(self, *args, **options):
        jobs = []
        for db_alias in settings.DATABASES.keys():
            print '\n======================= Migrating DB: {} ======================='.format(db_alias)

            if options['interactive']:
                # run synchronously
                call_command(
                    'migrate',
                    database=db_alias,
                    interactive=options['interactive'],
                    fake=options['fake'],
                    list=options['list'],
                )
            else:
                # run asynchonously
                jobs.append(gevent.spawn(
                    call_command,
                    'migrate',
                    database=db_alias,
                    interactive=options['interactive'],
                    fake=options['fake'],
                    list=options['list'],
                ))

        gevent.joinall(jobs)

        success = True
        for job in jobs:
            if not job.successful():
                print 'Failed to migrate'
                print job.exception
                success = False

        if not success:
            sys.exit(1)
