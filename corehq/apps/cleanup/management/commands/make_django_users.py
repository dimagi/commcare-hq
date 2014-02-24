from django.core.management import BaseCommand
from corehq.apps.users.models import CouchUser


class Command(BaseCommand):
    """
        This command is probably not very robust and has only been tested with
        a freshly bootstrapped postgres DB
    """
    help = ("Makes django users for Couch Users that don't currently have one")

    def handle(self, *args, **options):
        for u in CouchUser.all():
            du = u.sync_to_django_user()
            du.save()