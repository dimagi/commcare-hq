import json
from django.core.management.base import BaseCommand
from toggle.models import Toggle

from corehq.apps.locations.models import SQLLocation
from corehq.apps.domain.models import Domain
from corehq.toggles import HIERARCHICAL_LOCATION_FIXTURE, NAMESPACE_DOMAIN


class Command(BaseCommand):
    help = """
    To migrate to new flat fixture for locations. Enable FF HIERARCHICAL_LOCATION_FIXTURE for
    apps with locations and having commtrack:enabled in app files
    The Feature Flag FLAT_LOCATION_FIXTURE should be removed after this
    """

    def handle(self, *args, **options):
        domains_having_locations = (
            SQLLocation.objects.order_by('domain').distinct('domain')
            .values_list('domain', flat=True)
        )
        domains_with_hierarchical_fixture = find_applications_with_hierarchical_fixture(
            domains_having_locations
        )
        toggle = Toggle.get(HIERARCHICAL_LOCATION_FIXTURE.slug)
        for domain in domains_with_hierarchical_fixture:
            toggle.add(domain, True, NAMESPACE_DOMAIN)


def find_applications_with_hierarchical_fixture(domains):
    search_string = 'commtrack:enabled'
    domain_with_application = {}
    for domain in domains:
        domain_obj = Domain.get_by_name(domain)
        for application in domain_obj.applications():
            raw_doc = json.dumps(application.get_db().get(application.id))
            if search_string in raw_doc:
                search_string[domain] = application.id
                continue
    return domain_with_application
