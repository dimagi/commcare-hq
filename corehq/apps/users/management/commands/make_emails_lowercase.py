from django.core.management import BaseCommand

from corehq.apps.users.models import CouchUser


class Command(BaseCommand):
    help = "Makes emails into lowercase"

    def handle(self, *args, **options):
        for couch_user in CouchUser.all():
            if couch_user.email and any(char.isupper() for char in couch_user.email):
                print couch_user.email
                couch_user.email = couch_user.email.lower()
                couch_user.save()
