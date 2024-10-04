import logging

from django.core.management.base import BaseCommand

from corehq.apps.users.analytics import get_role_user_count
from corehq.apps.users.models_role import Permission, UserRole


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Add access_web_apps permission to default mobile worker roles"

    def handle(self, **options):
        permission, created = Permission.objects.get_or_create(value='access_web_apps')
        roles_to_update = UserRole.objects.filter(is_commcare_user_default=True)
        total = roles_to_update.count()
        logger.info(f"Found {total} roles to update")
        for index, role in enumerate(roles_to_update):
            if index % 100 == 0:
                logger.info(f"Examining role {index} of {total}")
            permissions = role.permissions
            if not permissions.access_web_apps and not permissions.web_apps_list:
                count = get_role_user_count(role.domain, role.couch_id, web_users_only=True)
                if count == 0:
                    # Only update if role is limited to mobile workers, who already have access to web apps
                    permissions.access_web_apps = True
                    permissions.normalize(previous=role.permissions)
                    role.set_permissions(permissions.to_list())
