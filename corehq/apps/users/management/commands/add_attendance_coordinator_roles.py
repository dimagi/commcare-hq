from django.core.management.base import BaseCommand

from corehq.apps.users.models_role import UserRole
from corehq.apps.users.role_utils import UserRolePresets
from corehq.apps.accounting.models import Subscription
from corehq.apps.accounting.models import SoftwarePlanEdition


class Command(BaseCommand):
    help = "Adds the Attendance Coordinator role to domains on the pro, advanced and entrprise plans."

    def handle(self, **options):
        pro_or_higher_plan = [
            SoftwarePlanEdition.PRO,
            SoftwarePlanEdition.ADVANCED,
            SoftwarePlanEdition.ENTERPRISE
        ]

        domain_names = Subscription.visible_objects.filter(
            plan_version__plan__edition__in=pro_or_higher_plan,
            is_active=True,
        ).values_list('subscriber__domain', flat=True).distinct()

        role_name = UserRolePresets.ATTENDANCE_COORDINATOR
        domains_with_role = UserRole.objects.filter(
            name=role_name,
            domain__in=domain_names
        ).values_list('domain', flat=True)

        domain_names = set(domain_names)
        domains_with_role = set(domains_with_role)
        domains_without_role = domain_names.difference(domains_with_role)

        preset_permissions = UserRolePresets.PRIVILEGED_ROLES.get(role_name)()

        for domain in domains_without_role:
            UserRole.create(
                domain,
                role_name,
                permissions=preset_permissions
            )
