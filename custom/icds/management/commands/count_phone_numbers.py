import csv
from datetime import datetime

from django.core.management.base import BaseCommand

from corehq.form_processor.models import CommCareCaseSQL
from corehq.apps.locations.models import SQLLocation

DOMAIN = "icds-cas"
CASE_TYPE = "person"


class Command(BaseCommand):
    help = """
    Find counts of person cases with blank, invalid, or valid values for contact_phone_number.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'partitions',
            nargs='+',
        )

    def find_test_locations(self):
        test_locations = set()
        TEST_STATES = []
        for loc in SQLLocation.active_objects.filter(location_type__code='state', domain=DOMAIN):
            if loc.metadata.get('is_test_location') == 'test':
                TEST_STATES.append(loc.name)

        for location in SQLLocation.active_objects.filter(name__in=TEST_STATES, domain=DOMAIN):
            test_locations.update(location.get_descendants(include_self=True).values_list('location_id', flat=True))

        return test_locations

    def handle(self, partitions, **options):
        test_locations = self.find_test_locations()

        filename = 'phone_number_validity_counts_%s.csv' % datetime.utcnow()
        with open(filename, 'w') as output:
            writer = csv.writer(output)
            writer.writerow(['partition', 'total cases', 'phone number present', 'phone number valid'])

            total_persons = 0
            total_persons_with_phone_number = 0
            total_persons_with_valid_phone_number = 0
            for partition in partitions:
                self.stdout.write("querying partition: %s" % partition)

                base_query = CommCareCaseSQL.objects.using(partition)
                base_query = base_query.filter(domain=DOMAIN, type=CASE_TYPE, closed=False, deleted=False)
                base_query = base_query.exclude(owner_id__in=test_locations)

                persons = base_query.count()
                self.stdout.write("person cases: %s" % persons)
                total_persons += persons

                persons_with_phone_number = base_query.filter(case_json__regex="\"contact_phone_number\": \".+\"").count()
                self.stdout.write("phone number present: %s" % persons_with_phone_number)
                total_persons_with_phone_number += persons_with_phone_number

                persons_with_valid_phone_number = base_query.filter(case_json__regex="\"contact_phone_number\": \"91[6789][0-9]{9}\"").count()
                self.stdout.write("phone number valid: %s" % persons_with_valid_phone_number)
                total_persons_with_valid_phone_number += persons_with_valid_phone_number

                writer.writerow([partition, persons, persons_with_phone_number, persons_with_valid_phone_number])

        self.stdout.write("Results written to %s" % filename)
        self.stdout.write("Total person cases: %s" % total_persons)
        self.stdout.write("Total phone number present: %s" % total_persons_with_phone_number)
        self.stdout.write("Total phone number valid: %s" % total_persons_with_valid_phone_number)
