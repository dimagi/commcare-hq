from django.core.management.base import BaseCommand

from corehq.apps.users.models_sql import SQLPermission, SQLUserRole


class Command(BaseCommand):
    help = "Adds download_reports permission to user role if not already present."

    def handle(self, **options):
        permission, created = SQLPermission.objects.get_or_create(value='download_reports')
        num_roles_modified = 0
        all_roles = SQLUserRole.objects.all()
        roles_with_new_permission = SQLUserRole.objects.filter(rolepermission__permission_fk_id=permission.id)
        for role in all_roles.difference(roles_with_new_permission).iterator():
            rp, created = role.rolepermission_set.get_or_create(permission_fk=permission,
                                                                defaults={"allow_all": True})
            if created:
                role._migration_do_sync()
                num_roles_modified += 1
            if num_roles_modified % 5000 == 0:
                print("Updated {} roles".format(num_roles_modified))
