import csv
from django.core.management.base import BaseCommand
from corehq.apps.locations.models import SQLLocation
from corehq.util.log import with_progress_bar
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.case_utils import CASE_TYPE_PERSON


class Command(BaseCommand):
    field_names = [
    ]

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('parent_location_id')

    def handle(self, domain, parent_location_id, **options):
        self.domain = domain
        self.accessor = CaseAccessors(domain)
        self.location = SQLLocation.objects.get(domain=domain, location_id=parent_location_id)
        owner_ids = self.location.get_descendants(include_self=True).location_ids()

        filename = 'patients.csv'
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(self.field_names)

            person_ids = self.accessor.get_open_case_ids_in_domain_by_type(CASE_TYPE_PERSON, owner_ids)
            for person in with_progress_bar(self.accessor.iter_cases(person_ids)):
                if person.get_case_property(ENROLLED_IN_PRIVATE) == 'true':
                    self.add_person(person, writer)
        print "Wrote to {}".format(filename)

    def add_person(self, person, writer):
        return
