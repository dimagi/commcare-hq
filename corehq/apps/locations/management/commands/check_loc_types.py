import csv
import datetime

from django.core.management.base import BaseCommand

from corehq.apps.commtrack.models import StockState
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

    def check_for_duplicate_codes(self, domain_info, loc_types):
        if not len(loc_types) == len({lt.code for lt in loc_types}):
            domain_info.duplicate_loc_type_codes += 1
            self.stdout.write("  Duplicate location_type codes found\n")

    def check_single_parentage(self, domain_info, loc_types):
        for loc_type in loc_types:
            if len(loc_type.allowed_parents) != 1:
                domain_info.incorrect_number_of_parents += 1
                self.stdout.write(u"  {} doesn't have one parent: ({})\n"
                                  .format(loc_type.name, loc_type.allowed_parents))

    def _find_parent(self, parent_code, loc_types):
        for loc_type in loc_types:
            # Some domains have names and not codes. Fall back to that.
            if loc_type.code == parent_code or loc_type.name == parent_code:
                return loc_type
        self.stdout.write(u"  parent loc type {} not found".format(parent_code))

    def check_parentage(self, domain_info, loc_types):
        for loc_type in loc_types:
            visited = set()
            def step(lt):
                if lt.code in visited:
                    domain_info.loc_type_parentage_cycle += 1
                    self.stdout.write(u"  I found a cycle!!! {}\n"
                                      .format(loc_types))
                    return
                elif not lt.allowed_parents[0]:
                    return
                else:
                    visited.add(lt.code)
                    parent = self._find_parent(lt.allowed_parents[0], loc_types)
                    if not parent:
                        domain_info.parent_loc_types_not_found += 1
                        return
                    step(parent)
            step(loc_type)

    def check_loc_types(self, domain_info, loc_types):
        loc_type_codes = {loc_type.code for loc_type in loc_types}
        # Some domains have names and not codes. Fall back to that.
        loc_type_codes.update({loc_type.name for loc_type in loc_types})
        loc_types = (SQLLocation.objects
                     .filter(domain=domain_info.name)
                     .values_list('location_type', flat=True)
                     .order_by('location_type')
                     .distinct('location_type'))

        for loc_type in loc_types:
            if loc_type not in loc_type_codes:
                count = (SQLLocation.objects
                         .filter(domain=domain_info.name, location_type=loc_type)
                         .count())
                domain_info.loc_type_does_not_exist += 1
                self.stdout.write(
                    u"  loc_type {} does not exist ({} instances)\n"
                    .format(loc_type, count)
                )

    def get_stock_states(self, domain_obj):
        stock_states = (StockState.objects
                        .filter(sql_location__domain=domain_obj.name)
                        .count())
        if stock_states > 0:
            domain_obj.num_stock_states = stock_states
            self.stdout.write("  This domain has {} stock states!"
                              .format(stock_states))

    def _write_to_csv(self, headers, domains):
        filename = "check_loc_types-{}.csv".format(datetime.date.today())
        with open(filename, 'wb') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows([
                [getattr(domain, header) for header in headers]
                for domain in domains
            ])
        self.stdout.write("\nwrote output to {}\n".format(filename))

    def handle(self, *args, **options):
        headers = [
            'name',
            'num_stock_states',
            'duplicate_loc_type_codes',
            'incorrect_number_of_parents',
            'parent_loc_types_not_found',
            'loc_type_parentage_cycle',
            'loc_type_does_not_exist',
        ]
        DomainInfo = type('DomainInfo', (object,), {h: 0 for h in headers})

        domains = []
        for domain_obj in Domain.get_all():
            locs = SQLLocation.objects.filter(domain=domain_obj.name).exists()
            loc_types = domain_obj.location_types
            if not loc_types and not locs:
                continue

            domain_info = DomainInfo()
            domain_info.name = domain_obj.name
            self.stdout.write(u"[{}] - {}\n".format(domain_obj.name,
                                                    domain_obj._id))
            self.get_stock_states(domain_info)
            self.check_for_duplicate_codes(domain_info, loc_types)
            self.check_single_parentage(domain_info, loc_types)
            self.check_parentage(domain_info, loc_types)
            self.check_loc_types(domain_info, loc_types)
            domains.append(domain_info)

        self._write_to_csv(headers, domains)
