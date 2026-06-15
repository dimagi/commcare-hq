from django.core.management.base import BaseCommand

from corehq.const import USER_CHANGE_VIA_USER_REQUEST
from corehq.apps.users.models import WebUser
from corehq.apps.users.util import SYSTEM_USER_ID


class Command(BaseCommand):
    help = "Deletes the given user"

    def add_arguments(self, parser):
        parser.add_argument('username')

    def handle(self, username, **options):
        print("Deleting user %s" % username)
        WebUser.get_by_username(username).delete(
            deleted_by_domain=None,
            deleted_by=SYSTEM_USER_ID,
            deleted_via=USER_CHANGE_VIA_USER_REQUEST,
        )
        print("Operation completed")
