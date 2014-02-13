from django.core.management.base import BaseCommand, CommandError
from corehq.apps.cleanup.xforms import reprocess_form_cases
from couchforms import fetch_and_wrap_form
import csv
from corehq.apps.cleanup.management.commands.generate_form_case_consistency_list import HEADERS

class Command(BaseCommand):
    args = '<file>'
    help = ('Reprocesses a set of forms, by passing in a file '
            '(which should be a paired-down version of the output '
            'of repair_unprocessed_forms')

    def handle(self, *args, **options):
        if len(args) == 1:
            filename = args[0]
        else:
            raise CommandError('Usage: %s\n%s' % (self.args, self.help))

        doc_id_index = HEADERS.index('doc_id')
        domain_index = HEADERS.index('domain')
        with open(filename, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                domain = row[domain_index]
                doc_id = row[doc_id_index]
                # don't process the header row
                if doc_id == "doc_id": 
                    continue

                print 'reprocessing form %s in domain %s' % (doc_id, domain)
                form = fetch_and_wrap_form(doc_id)
                try:
                    reprocess_form_cases(form)
                except AssertionError:
                    print 'form %s FAILED' % doc_id

