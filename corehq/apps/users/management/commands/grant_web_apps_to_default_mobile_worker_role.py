from django.core.management.base import BaseCommand

from corehq.apps.users.models_role import Permission, UserRole


class Command(BaseCommand):
    help = "Add access_web_apps permission to default mobile worker roles"

    def handle(self, **options):
        permission, created = Permission.objects.get_or_create(value='access_web_apps')
        roles_to_update = UserRole.objects.filter(is_commcare_user_default=True)
        #roles_to_update = roles_to_update.exclude(rolepermission__permission_fk_id=permission.id)
        for role in roles_to_update:
            permissions = role.permissions
            if not permissions.access_web_apps and not permissions.web_apps_list:
                permissions.access_web_apps = True
                permissions.normalize(previous=role.permissions)
                role.set_permissions(permissions.to_list())
