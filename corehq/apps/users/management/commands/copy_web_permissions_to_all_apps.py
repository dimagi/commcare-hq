from django.core.management.base import BaseCommand

from dimagi.utils.couch.database import iter_docs

from corehq.apps.users.models import UserRole


class Command(BaseCommand):
    help = """Copy permissions of view_web_apps to access_all_apps and view_web_apps_list to
    allowed_app_list"""

    def handle(self, **options):
        roles = UserRole.view(
            'users/roles_by_domain',
            include_docs=False,
            reduce=False
        ).all()
        counter = 0
        total_doc_count = 0
        for role_doc in iter_docs(UserRole.get_db(), [r['id'] for r in roles]):
            role = UserRole.wrap(role_doc)
            total_doc_count += 1
            changed = False
            permissions = role_doc['permissions']
            if permissions.get('access_all_apps') != permissions.get('view_web_apps'):
                role.permissions.access_all_apps = permissions.get('view_web_apps', True)
                changed = True
            if permissions.get('allowed_app_list') != permissions.get('view_web_apps_list'):
                role.permissions.allowed_app_list = permissions.get('view_web_apps_list', [])
                changed = True
            if changed:
                counter += 1
                role.save()
        print(f"{counter} of {total_doc_count} roles updated")
