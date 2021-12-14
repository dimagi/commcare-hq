from datetime import datetime
import logging
import csv

from django.core.management.base import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.apps.users.models_role import RolePermission, UserRole
from corehq.toggles import RESTRICT_MOBILE_ACCESS

logger = logging.getLogger('app_migration')
logger.setLevel('INFO')


class Command(BaseCommand):
    help = "Removes the mobile access permission from roles not in Domains with the" \
           " RESTRICT_MOBILE_ACCESS feature flag and outputs details of deleted RolePermission" \
           " objects to a csv file."


    def handle(self, **options):
        self.outfile = f"Mobile_access_permission_deleted_{datetime.today().strftime('%m-%d-%Y')}.csv"

        domains_with_mobile_permission = self._get_domains_with_mobile_permission()
        num_domains_with_their_roles_changed = self._delete_mobile_permissions_from_domains(
            domains_with_mobile_permission)
        print(f"Done: {num_domains_with_their_roles_changed} domains out of {len(Domain.get_all_names())} total"
            " domains had permissions for their roles changed by this command execution.")

    def _delete_mobile_permissions_from_domains(self, domains):
        num_domains_with_their_roles_changed = 0
        csvfile = open(self.outfile, "wt")
        self.writer = csv.writer(csvfile)
        self.writer.writerow(["Mobile access permission has been deleted for the following roles."])
        self.writer.writerow(["Related Role", "Domain"])
        for domain in domains:
            did_delete_permisisons_from_domain = self._delete_mobile_access_permissions_on_domain(domain)
            if did_delete_permisisons_from_domain:
                num_domains_with_their_roles_changed += 1
        csvfile.close()
        return num_domains_with_their_roles_changed

    def _delete_mobile_access_permissions_on_domain(self, domain):
        affected_roles = UserRole.objects.filter(
            domain=domain, rolepermission__permission_fk__value='access_mobile_endpoints')
        atleast_one_permission_deleted = 0 < len(affected_roles)
        for role in affected_roles:
            self.writer.writerow([
                role.name,
                domain
            ])
        role_ids = [role.id for role in affected_roles]
        RolePermission.objects.filter(
            role__id__in=role_ids,
            permission_fk__value='access_mobile_endpoints'
        ).delete()
        logger.info('Roles successfully deleted.')
        return atleast_one_permission_deleted

    @staticmethod
    def _get_domains_with_mobile_permission():
        domains_with_restriction_on = RESTRICT_MOBILE_ACCESS.get_enabled_domains()
        domains_with_mobile_permission_unfiltered = UserRole.objects.filter(
            rolepermission__permission_fk__value='access_mobile_endpoints'
        ).values_list('domain', flat=True).distinct()
        return [domain for domain in domains_with_mobile_permission_unfiltered if (
            domain not in domains_with_restriction_on
            and not Domain.get_by_name(domain).restrict_mobile_access
        )]
