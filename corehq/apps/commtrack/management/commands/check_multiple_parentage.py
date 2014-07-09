from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write("Populating site codes...\n")

        domains = Domain.get_all()

        for d in domains:
            if d.commtrack_enabled:
                for loc_type in d.commtrack_settings.location_types:
                    if len(loc_type.allowed_parents) > 1:
                        self.stdout.write(
                            "Found multiple parent options in domain: " +
                            d.name
                        )
