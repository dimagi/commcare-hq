from django.core.management.base import BaseCommand
from corehq.apps.users.models import WebUser


class Command(BaseCommand):
    help = "Deletes the given user"

    def add_arguments(self, parser):
        parser.add_argument('username')

    def handle(self, username, **options):
        print("Deleting user %s" % username)
        WebUser.get_by_username(username).delete()
        print("Operation completed")
