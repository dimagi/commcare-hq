from django.core.management.base import BaseCommand

from corehq.apps.users.dbaccessors import get_all_role_ids
from dimagi.utils.couch.database import iter_docs

from corehq.apps.users.models import UserRole


class Command(BaseCommand):
    help = """"Migrate UserRole to accommodate additional view options and
    permissions splits"""

    def handle(self, **options):
        for role_doc in iter_docs(UserRole.get_db(), get_all_role_ids()):
            role = UserRole.wrap(role_doc)
            save_role = False

            if role.permissions.edit_web_users:
                role.permissions.view_web_users = True
                role.permissions.view_roles = True
                save_role = True

            if role.permissions.edit_commcare_users:
                role.permissions.view_commcare_users = True
                role.permissions.edit_groups = True
                role.permissions.view_groups = True
                save_role = True

            if role.permissions.edit_locations:
                role.permissions.view_locations = True
                save_role = True

            if save_role:
                role.save()
