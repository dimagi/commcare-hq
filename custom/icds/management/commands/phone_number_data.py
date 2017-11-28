from __future__ import print_function

from __future__ import absolute_import
import csv

from django.core.management import BaseCommand

from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('infile')
        parser.add_argument('outfile')

    def handle(self, infile, outfile, *args, **options):
        self.case_accessor = CaseAccessors('icds-cas')
        with open(infile, 'r') as old, open(outfile, 'w') as new:
            reader = csv.reader(old)
            writer = csv.writer(new)
            headers = next(reader)
            writer.writerow(headers)
            for row in reader:
                owner = row[2]
                case_id = row[3]
                hh_id = row[4]
                if hh_id:
                    person, hh = self.case_accessor.get_cases([case_id, hh_id], ordered=True)
                else:
                    person = self.case_accessor.get_case(case_id)
                    hh = None
                row[15] = SQLLocation.objects.get(location_id=owner).name
                if hh:
                    row[16] = hh.get_case_property('name')
                    row[17] = hh.get_case_property('hh_num')
                row[18] = person.get_case_property('name')
                row[19] = person.get_case_property('dob')
                row[20] = person.get_case_property('sex')
                writer.writerow(row)
