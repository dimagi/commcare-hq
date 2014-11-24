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
                toggle = Toggle.get(LOCATIONS.slug)
                toggle_user_key = namespaced_item(domain.name, NAMESPACE_DOMAIN)

                if toggle_user_key not in toggle.enabled_users:
                    toggle.enabled_users.append(toggle_user_key)
                    toggle.save()
                    update_toggle_cache(LOCATIONS.slug, toggle_user_key, True)

                if not domain.locations_enabled:
                    domain.locations_enabled = True
                    domain.save()
