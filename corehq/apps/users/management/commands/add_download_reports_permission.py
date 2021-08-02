from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked
from corehq.apps.users.models import SQLPermission, SQLUserRole


class Command(BaseCommand):
    help = "Adds download_reports permission to user role if not already present."

    def handle(self, **options):
        permission, created = SQLPermission.objects.get_or_create(value='download_reports')
        num_roles_modified = 0
        all_role_ids = set(SQLUserRole.objects.all().values_list("id", flat=True))
        role_ids_with_new_permission = set(SQLUserRole.objects.filter(rolepermission__permission_fk_id=permission.id)
                                           .values_list("id", flat=True))
        difference = all_role_ids.difference(role_ids_with_new_permission)
        for chunk in chunked(difference, 50):
            for role in SQLUserRole.objects.filter(id__in=chunk):
                rp, created = role.rolepermission_set.get_or_create(permission_fk=permission,
                                                                    defaults={"allow_all": True})
                if created:
                    num_roles_modified += 1
                if num_roles_modified % 5000 == 0:
                    print("Updated {} roles".format(num_roles_modified))
