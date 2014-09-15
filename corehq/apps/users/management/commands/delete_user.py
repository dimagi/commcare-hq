from django.core.management.base import BaseCommand, CommandError
from corehq.apps.users.models import WebUser


class Command(BaseCommand):
    help = "Deletes the given user"
    args = '<user>'

    def handle(self, *args, **options):
        user = args[0].strip()
        print "Deleting user %s" % user
        WebUser.get_by_username(user).delete()
        print "Operation completed"
