from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import textwrap
from django.contrib.auth.management.commands.createsuperuser import Command as CreatesuperuserCommand
import time


class Command(CreatesuperuserCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument('--force', action='store_true',
                            help='Run the django default createsuperuser')

    def handle(self, *args, **options):
        if options['force']:
            del options['force']
            super(Command, self).handle(*args, **options)
        else:
            print()
            print("The createsuperuser command isn't recommended for use in this project.")
            print()
            time.sleep(2)
            print(textwrap.dedent(
                """
                Please use `./manage.py make_superuser` instead.

                If you really want to use the django built-in createsuperuser management command,
                you can always run `./manage.py createsuperuser --force`.
                """
            ))
            exit(1)
