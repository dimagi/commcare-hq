from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation


EXCLUDE_DOMAINS = (
    "drewpsi",
    "psi",
    "psi-ors",
    "psi-test",
    "psi-test2",
    "psi-test3",
    "psi-unicef",
    "psi-unicef-wb",
)


class Command(BaseCommand):
    help = 'Check for consistency between location types and locations'

    def check_for_duplicate_codes(self, loc_types):
        if not len(loc_types) == len({lt.code for lt in loc_types}):
            self.stdout.write("  Duplicate location_type codes found\n")

    def check_single_parentage(self, loc_types):
        for loc_type in loc_types:
            if len(loc_type.allowed_parents) != 1:
                self.stdout.write(u"  {} doesn't have one parent: ({})\n"
                                  .format(loc_type.name, loc_type.allowed_parents))

    def _find_parent(self, parent_code, loc_types):
        for loc_type in loc_types:
            # Some domains have names and not codes. Fall back to that.
            if loc_type.code == parent_code or loc_type.name == parent_code:
                return loc_type
        self.stdout.write(u"  parent loc type {} not found".format(parent_code))

    def check_parentage(self, loc_types):
        for loc_type in loc_types:
            visited = set()
            def step(lt):
                if lt.code in visited:
                    self.stdout.write(u"  I found a cycle!!! {}\n"
                                      .format(loc_types))
                    return
                elif not lt.allowed_parents[0]:
                    return
                else:
                    visited.add(lt.code)
                    parent = self._find_parent(lt.allowed_parents[0], loc_types)
                    if not parent:
                        return
                    step(parent)
            step(loc_type)

    def check_loc_types(self, domain, loc_types):
        loc_type_codes = {loc_type.code for loc_type in loc_types}
        # Some domains have names and not codes. Fall back to that.
        loc_type_codes.update({loc_type.name for loc_type in loc_types})
        loc_types = (SQLLocation.objects
                     .filter(domain=domain)
                     .values_list('location_type', flat=True)
                     .order_by('location_type')
                     .distinct('location_type'))

        for loc_type in loc_types:
            if loc_type not in loc_type_codes:
                count = (SQLLocation.objects
                         .filter(domain=domain, location_type=loc_type)
                         .count())
                self.stdout.write(
                    u"  loc_type {} does not exist ({} instances)\n"
                    .format(loc_type, count)
                )

    def handle(self, *args, **options):
        for domain_obj in Domain.get_all():
            loc_types = domain_obj.location_types
            locs = SQLLocation.objects.filter(domain=domain_obj.name).exists()
            if not loc_types and not locs:
                continue
            self.stdout.write(u"[{}] - {}\n".format(domain_obj.name,
                                                    domain_obj._id))
            self.check_for_duplicate_codes(loc_types)
            self.check_single_parentage(loc_types)
            self.check_parentage(loc_types)
            self.check_loc_types(domain_obj.name, loc_types)
