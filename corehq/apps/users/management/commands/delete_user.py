import sys
from getpass import getpass

from django.contrib.auth import authenticate
from django.core.management.base import BaseCommand

from corehq.apps.users.models import WebUser


class Command(BaseCommand):
    help = "Deletes the given user"

    def add_arguments(self, parser):
        parser.add_argument('username')

    def handle(self, username, **options):
        print("Authenticate:")
        user_username = input("Please enter your username: ")
        user_password = getpass()
        user = authenticate(username=user_username, password=user_password)
        if user is None or not user.is_active:
            print(f"Invalid username or password")
            sys.exit(1)

        web_user = WebUser.get_by_username(username)
        if not web_user:
            print(f"User '{username}' not found")
        else:
            print("Deleting user %s" % username)
            web_user.delete(deleted_by=user, deleted_via=__name__)
            print("Operation completed")
