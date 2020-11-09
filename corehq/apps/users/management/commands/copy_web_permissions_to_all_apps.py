from django.core.management.base import BaseCommand

from corehq.apps.users.models import UserRole
from corehq.util.couch import DocUpdate, iter_update
from corehq.util.log import with_progress_bar


def _copy_permissions(role_doc):
    role = UserRole.wrap(role_doc)
    permissions = role_doc['permissions']
    if permissions.get('access_all_apps') != permissions.get('view_web_apps'):
        role.permissions.access_all_apps = permissions.get('view_web_apps', True)
    if permissions.get('allowed_app_list') != permissions.get('view_web_apps_list'):
        role.permissions.allowed_app_list = permissions.get('view_web_apps_list', [])
    return DocUpdate(role)


class Command(BaseCommand):
    help = """Copy permissions of view_web_apps to access_all_apps and view_web_apps_list to
    allowed_app_list"""

    def handle(self, **options):
        roles = UserRole.view(
            'users/roles_by_domain',
            include_docs=False,
            reduce=False
        ).all()
        role_ids = [role['id'] for role in roles]
        iter_update(UserRole.get_db(), _copy_permissions, with_progress_bar(role_ids), chunksize=1)
