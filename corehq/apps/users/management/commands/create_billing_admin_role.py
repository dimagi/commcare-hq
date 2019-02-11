from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import UserRole, UserRolePresets


class Command(BaseCommand):
    help = ("Adds the billing admin preset role to all existing domains")

    def handle(self, **options):
        for domain_obj in Domain.get_all():
            UserRole.get_or_create_with_permissions(
                domain_obj.name,
                UserRolePresets.get_permissions(UserRolePresets.BILLING_ADMIN),
                UserRolePresets.BILLING_ADMIN
            )
