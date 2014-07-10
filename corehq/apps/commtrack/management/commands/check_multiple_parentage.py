from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location
import csv


class Command(BaseCommand):
    def handle(self, *args, **options):
        with open('parentage_results.csv', 'wb+') as csvfile:
            csv_writer = csv.writer(
                csvfile,
                delimiter=',',
                quotechar='|',
                quoting=csv.QUOTE_MINIMAL
            )

            csv_writer.writerow([
                'id',
                'name',
                'is_test',
                'location_type',
                'number_of_offending_locations',
            ])

            domains = Domain.get_all()

            for d in domains:
                if d.commtrack_enabled:
                    for loc_type in d.commtrack_settings.location_types:
                        if len(loc_type.allowed_parents) > 1:
                            count = len(list(
                                Location.filter_by_type(
                                    d.name,
                                    loc_type.name,
                                )
                            ))

                            csv_writer.writerow([
                                d._id,
                                d.name,
                                d.is_test,
                                loc_type.name,
                                count
                            ])
