from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Return the first superuser, or a non-zero result."

    def handle(self, **options):
        user = User.objects.filter(is_superuser=True).first()
        if user:
            self.stdout.write(f'The first superuser is {user}')
        else:
            # A non-zero exit code makes this easy to use in shell scripts
            raise CommandError('Superuser not found')
