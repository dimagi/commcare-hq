from __future__ import print_function
from optparse import make_option

from django.core.management.base import BaseCommand
from toggle.models import Toggle

from corehq.apps.locations.models import SQLLocation, LocationFixtureConfiguration
from corehq.toggles import HIERARCHICAL_LOCATION_FIXTURE, NAMESPACE_DOMAIN, FLAT_LOCATION_FIXTURE


class Command(BaseCommand):
    help = """
    To migrate to new flat fixture for locations. Enable FF HIERARCHICAL_LOCATION_FIXTURE for
    apps with locations and not enabled with Flat fixture flag and set their configuration to use hierarchical
    fixture format.
    The Feature Flag FLAT_LOCATION_FIXTURE should be removed after this
    """
    option_list = BaseCommand.option_list + (
        make_option("--check",
                    action="store_true",
                    dest="check",
                    default=False,
                    help="Include this option to check what changes would occur and highlight domains that need "
                         "attention"),
    )

    def handle(self, *args, **options):
        dry_run = options['check']

        # 1. Find domains with locations
        domains_having_locations = (
            SQLLocation.objects.order_by('domain').distinct('domain')
            .values_list('domain', flat=True)
        )
        print("Domain having locations(%s): %s" % (len(domains_having_locations), domains_having_locations))
        # 2. Find domains on flat fixture
        domain_with_flat_fixture_enabled = find_domains_with_flat_fixture_enabled()
        print("Domain with flat fixture enabled(%s): %s" % (len(domain_with_flat_fixture_enabled),
                                                            domain_with_flat_fixture_enabled))

        # 3. Find domains to stay on legacy fixture
        domains_to_stay_on_hierarchical_fixture = (set(domains_having_locations) -
                                                   set(domain_with_flat_fixture_enabled))
        print("Domain to stay on hierarchical fixture(%s): %s" % (len(domains_to_stay_on_hierarchical_fixture),
                                                                  domains_to_stay_on_hierarchical_fixture))

        # 4. Update domains that need to stay on hierarchical with enabled legacy toggle to be able to access conf
        # and update their location configuration to use hierarchical fixture for now
        for domain in domains_to_stay_on_hierarchical_fixture:
            if not dry_run:
                print("Setting HIERARCHICAL_LOCATION_FIXTURE toggle for domain: %s" % domain)
                HIERARCHICAL_LOCATION_FIXTURE.set(domain, True, NAMESPACE_DOMAIN)
            else:
                print("HIERARCHICAL_LOCATION_FIXTURE toggle would be set for domain: %s" % domain)

            if not dry_run:
                print("Enabling legacy fixture for domain: %s" % domain)
                location_configuration = LocationFixtureConfiguration.for_domain(domain)
                print("Current Configuration, Persisted: %s, Use Flat fixture: %s, Use Hierarchical fixture %s" % (
                    not location_configuration._state.adding, location_configuration.sync_hierarchical_fixture,
                    location_configuration.sync_flat_fixture))

                enable_legacy_fixture_for_domain(domain)
            else:
                print("Legacy fixture to be enabled for domain: %s" % domain)
                location_configuration = LocationFixtureConfiguration.for_domain(domain)
                print("Current Configuration, Persisted: %s, Use Flat fixture: %s, Use Hierarchical fixture %s" % (
                    not location_configuration._state.adding, location_configuration.sync_hierarchical_fixture,
                    location_configuration.sync_flat_fixture))

        # 5. Domains that need to stay on flat fixture need not worry about any change since they would
        # default to flat fixture but must ensure if they don't have conf set for using hierarchical fixture
        for domain in domain_with_flat_fixture_enabled:
            # For domains with flat fixture enabled and have configuration defined to use hierarchical fixture
            # Notify them to make their state clear
            location_conf_for_domain = LocationFixtureConfiguration.for_domain(domain)
            if not location_conf_for_domain._state.adding and location_conf_for_domain.sync_hierarchical_fixture:
                # Can use the following to update them
                # location_conf_for_domain.sync_flat_fixture = True
                # location_conf_for_domain.sync_hierarchical_fixture = False
                # location_conf_for_domain.save()
                print("Domain that needs attention since its not in a definite state: %s" % domain)


def enable_legacy_fixture_for_domain(domain):
    location_configuration = LocationFixtureConfiguration.for_domain(domain)
    location_configuration.sync_hierarchical_fixture = True
    location_configuration.sync_flat_fixture = False
    location_configuration.save()


def find_domains_with_flat_fixture_enabled():
    toggle = Toggle.get(FLAT_LOCATION_FIXTURE.slug)
    enabled_users = toggle.enabled_users
    return [user.split('domain:')[1] for user in enabled_users if 'domain:' in user]
