from django.core.management.base import BaseCommand

from corehq.apps.users.models import UserRole
from corehq.util.couch import DocUpdate, iter_update
from corehq.util.log import with_progress_bar


def _copy_permissions(role_doc):
    role = UserRole.wrap(role_doc)
    changed = False
    permissions = role_doc['permissions']
    if permissions.get('access_all_apps') != permissions.get('view_web_apps'):
        role.permissions.access_all_apps = permissions.get('view_web_apps', True)
        changed = True
    if permissions.get('allowed_app_list') != permissions.get('view_web_apps_list'):
        role.permissions.allowed_app_list = permissions.get('view_web_apps_list', [])
        changed = True
    if changed:
        return DocUpdate(role)


def _get_role_ids(roles):
    return [role['id'] for role in roles]


class Command(BaseCommand):
    help = """Copy permissions of view_web_apps to access_all_apps and view_web_apps_list to
    allowed_app_list"""

    def handle(self, **options):
        roles = UserRole.view(
            'users/roles_by_domain',
            include_docs=False,
            reduce=False
        ).all()
        role_ids = _get_role_ids(roles)
        iter_update(UserRole.get_db(), _copy_permissions, with_progress_bar(role_ids), chunksize=2)
