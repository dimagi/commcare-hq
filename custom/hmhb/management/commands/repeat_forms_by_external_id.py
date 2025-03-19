"""
To run this command for a CSV file of external IDs (e.g. tracked entity
instance UIDs):

Get the external IDs (assuming they are in the first column)::

    $ cat my_csv_file.csv | cut -d, -f1

Iterate them, and run this command for each one::

    $ for extid in `cat my_csv_file.csv | cut -d, -f1`
      do
          ./manage.py repeat_forms_by_external_id \
              my-domain \
              abc123def456 \
              $extid \
              my-case-type
      done

"""
from django.core.management.base import BaseCommand

from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.motech.repeaters.models import Repeater


class Command(BaseCommand):
    help = ('Finds the case identified by `external_id`, and triggers '
            'a repeater for each form that updated that case.')

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('repeater_id')
        parser.add_argument('external_id')
        parser.add_argument('case_type')

    def handle(self, *args, **options):
        repeater = Repeater.objects.get(id=options['repeater_id'])
        assert repeater.domain == options['domain'], 'Repeater not found'

        case = CommCareCase.objects.get_case_by_external_id(
            options['domain'],
            options['external_id'],
            options['case_type'],
            raise_multiple=True,
        )
        assert case, f'Case {options["external_id"]!r} not found'

        form_ids = [tx.form_id for tx in case.get_form_transactions()]
        for form in XFormInstance.objects.get_forms(form_ids, ordered=True):
            repeater.register(form)
