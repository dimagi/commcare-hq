from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location


class Command(BaseCommand):
    def is_still_default_outlet_config(self, outlet):
        return set(outlet.allowed_parents) == set(['village', 'block'])

    def find_outlet_type(self, location_types):
        outlet = [t for t in location_types if t.code == 'outlet']

        if outlet:
            return outlet[0]
        else:
            return []

    def any_bad_outlets(self, domain):
        outlets = Location.filter_by_type(domain.name, 'outlet')
        for outlet in outlets:
            if outlet.parent.location_type == 'block':
                return True

        return False

    def handle(self, *args, **options):
        domains = Domain.get_all()

        error_domains = []

        for d in domains:
            if d.commtrack_enabled:
                outlet = self.find_outlet_type(d.commtrack_settings.location_types)
                if outlet:
                    if self.is_still_default_outlet_config(outlet):
                        if self.any_bad_outlets(d):
                            self.stdout.write(
                                "\nDomain " + d.name + " still has outlets mapped to blocks"
                            )
                        else:
                            outlet.allowed_parents = ['village']
                            d.commtrack_settings.save()
                            self.stdout.write("\nFixed domain " + d.name)
                    elif len(outlet.allowed_parents) > 1:
                        # if it was no longer the default setup, but does
                        # have multiple parent options, we will need to
                        # fix manually
                        error_domains.append(d.name)

        if error_domains:
            self.stdout.write(
                "\nThe following domains had outlet types that could not "
                "be corrected:\n" + '\n'.join(error_domains)
            )
