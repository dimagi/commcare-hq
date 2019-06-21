from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.apps.users.models import UserRole
from dimagi.utils.couch.database import iter_docs


class Command(BaseCommand):
    help = """"Migrate UserRole to accommodate additional view options and
    permissions splits"""

    def handle(self, **options):
        roles = UserRole.view(
            'users/roles_by_domain',
            include_docs=False,
            reduce=False
        ).all()
        for role_doc in iter_docs(UserRole.get_db(), [r['id'] for r in roles]):
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
