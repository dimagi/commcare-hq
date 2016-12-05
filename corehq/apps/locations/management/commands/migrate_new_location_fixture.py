from django.core.management.base import BaseCommand
from toggle.models import Toggle

from corehq.apps.locations.models import LocationFixtureConfiguration, SQLLocation
from corehq.toggles import FLAT_LOCATION_FIXTURE


class Command(BaseCommand):
    help = """
    To migrate to new flat fixture for locations. Update apps with locations and not having
    FLAT_LOCATION_FIXTURE enabled to have LocationFixtureConfiguration with
    sync_hierarchical_fixture True and sync_flat_fixture False to have old fixtures enabled.
    The Feature Flag should be removed after this
    """

    def handle(self, *args, **options):
        domains_having_locations = set(SQLLocation.objects.values_list('domain', flat=True))
        toggle = Toggle.get(FLAT_LOCATION_FIXTURE.slug)
        enabled_users = toggle.enabled_users
        enabled_domains = [user.split('domain:')[1] for user in enabled_users]
        for domain_name in domains_having_locations:
            if domain_name not in enabled_domains:
                domain_config = LocationFixtureConfiguration.for_domain(domain_name)
                # update configs that had not been changed which means both values are at default True
                if domain_config.sync_hierarchical_fixture and domain_config.sync_flat_fixture:
                    # update them to use hierarchical fixture
                    domain_config.sync_flat_fixture = False
                    domain_config.sync_hierarchical_fixture = True
                    domain_config.save()
