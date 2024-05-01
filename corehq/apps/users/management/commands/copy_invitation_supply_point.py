from django.core.management.base import BaseCommand

from corehq.apps.domain_migration_flags.api import (
    ALL_DOMAINS,
    get_migration_status,
    set_migration_complete,
    set_migration_started,
)
from corehq.apps.domain_migration_flags.exceptions import (
    DomainMigrationProgressError,
)
from corehq.util.log import with_progress_bar
from corehq.apps.domain_migration_flags.models import MigrationStatus
from corehq.apps.users.models import Invitation
from corehq.apps.locations.models import SQLLocation
from corehq.util.queries import queryset_to_iterator

MIGRATION_SLUG = "users_invitation_copy_supply_point_to_location_field"


class Command(BaseCommand):
    help = "Copies invitation supply_point field to location field."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", default=False,
                            help="Run the queries even if the migration has been marked complete.")

    def handle(self, **options):
        force = options["force"]
        status = get_migration_status(ALL_DOMAINS, MIGRATION_SLUG)
        if status == MigrationStatus.COMPLETE and not force:
            self.stderr.write("Copying supply point field to location field has already been marked as complete")
            return
        if status not in (MigrationStatus.IN_PROGRESS, MigrationStatus.COMPLETE):
            set_migration_started(ALL_DOMAINS, MIGRATION_SLUG)

        _copy_supply_point_field_to_location()

        try:
            set_migration_complete(ALL_DOMAINS, MIGRATION_SLUG)
        except DomainMigrationProgressError:
            if not force:
                raise


def _copy_supply_point_field_to_location():
    invitations_queryset = (Invitation.objects
                            .exclude(supply_point__isnull=True)
                            .filter(location__isnull=True))
    for invitation in with_progress_bar(
            queryset_to_iterator(invitations_queryset, Invitation), invitations_queryset.count()):
        invitation.location = SQLLocation.by_location_id(invitation.supply_point)
        invitation.save()
