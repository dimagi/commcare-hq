import csv

from django.core.management import BaseCommand

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('infile')
        parser.add_argument('outfile')

    def handle(self, infile, outfile, *args, **options):
        self.case_accessor = CaseAccessors('icds-cas')
        with open(infile, 'r', encoding='utf-8') as old, open(outfile, 'w', encoding='utf-8') as new:
            reader = csv.reader(old)
            writer = csv.writer(new)
            headers = next(reader)
            writer.writerow(headers)
            for row in reader:
                case_id = row[4]
                hh_id = row[10]
                if hh_id:
                    person, hh = self.case_accessor.get_cases([case_id, hh_id], ordered=True)
                else:
                    person = self.case_accessor.get_case(case_id)
                    hh = None
                if hh:
                    row[18] = hh.get_case_property('name')
                    row[19] = hh.get_case_property('hh_num')
                row[20] = person.get_case_property('name')
                writer.writerow(row)
