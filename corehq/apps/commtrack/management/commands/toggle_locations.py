from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain
from corehq.feature_previews import LOCATIONS
from corehq.toggles import NAMESPACE_DOMAIN
from toggle.shortcuts import update_toggle_cache, namespaced_item
from toggle.models import Toggle


class Command(BaseCommand):
    def handle(self, *args, **options):
        domains = Domain.get_all()

        for domain in domains:
            if domain.commtrack_enabled:
                LOCATIONS.set(domain.name, True, NAMESPACE_DOMAIN)
                if not domain.locations_enabled:
                    domain.locations_enabled = True
                    domain.save()
