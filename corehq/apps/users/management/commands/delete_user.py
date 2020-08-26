import sys

from django.core.management.base import BaseCommand

from corehq.apps.users.models import WebUser


class Command(BaseCommand):
    help = "Deletes the given user"

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--deleted_by', required=True)

    def handle(self, username, deleted_by, **options):
        user_to_delete = _get_user(username)
        deleted_by_user = _get_user(deleted_by)
        print("Deleting user %s" % username)
        user_to_delete.delete(deleted_by=deleted_by_user, deleted_via=__name__)
        print("Operation completed")


def _get_user(username):
    user = WebUser.get_by_username(username)
    if not user:
        print(f"User '{username}' not found")
        sys.exit(1)
    return user
