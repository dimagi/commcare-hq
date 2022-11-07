import sys

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Return the first superuser, or a non-zero result."

    def handle(self, **options):
        if not settings.ALLOW_MAKE_SUPERUSER_COMMAND:
            self.stdout.write('This command is not applicable to this '
                              'environment.')
            sys.exit()

        user = User.objects.filter(is_superuser=True).first()
        if user:
            self.stdout.write(f'The first superuser is {user}')
        else:
            raise CommandError('Superuser not found')
