from django.core.management.base import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.apps.users.models_role import RolePermission, UserRole
from corehq.toggles import RESTRICT_MOBILE_ACCESS


class Command(BaseCommand):
    help = "Removes the mobile access permission from roles not in Domains with" \
           " the RESTRICT_MOBILE_ACCESS feature flag"

    def handle(self, **options):
        num_domains_with_their_roles_changed = 0
        domains_with_restriction_on = RESTRICT_MOBILE_ACCESS.get_enabled_domains()
        for domain in Domain.get_all_names():
            if domain not in domains_with_restriction_on and not Domain.get_by_name(domain).restrict_mobile_access:
                permission_was_removed_for_domain = None
                for role in UserRole.objects.get_by_domain(domain):
                    did_mobile_access_permission_exist = self._delete_mobile_access_permission_if_exists(role)
                    if(did_mobile_access_permission_exist):
                        permission_was_removed_for_domain = True
                if(permission_was_removed_for_domain):
                    num_domains_with_their_roles_changed += 1
        print(f"Done: {num_domains_with_their_roles_changed} domains out of {len(Domain.get_all_names())} total"
            " domains had permissions for their roles changed by this command execution.")

    @staticmethod
    def _delete_mobile_access_permission_if_exists(role):
        did_mobile_access_permission_exist = None
        mobile_endpoints_rp = ([rp for rp in role.rolepermission_set.all()
                                if rp.permission == 'access_mobile_endpoints'])
        if mobile_endpoints_rp:
            did_mobile_access_permission_exist = True
            mobile_endpoints_rp_id = mobile_endpoints_rp[0].id
            RolePermission.objects.filter(id=mobile_endpoints_rp_id).delete()
        return did_mobile_access_permission_exist
