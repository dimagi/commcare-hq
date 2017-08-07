import csv
import json

from django.core.management.base import BaseCommand

from corehq.util.log import with_progress_bar
from corehq.motech.repeaters.dbaccessors import iter_repeat_records_by_domain, get_repeat_record_count


class Command(BaseCommand):
    help = """
    Output a CSV file of incentive payloads that were sent to BETS in repeater <repeater_id>.

    This should be run once for each incentive type:
    - BETS180TreatmentRepeater
    - BETSDrugRefillRepeater
    - BETSSuccessfulTreatmentRepeater
    - BETSDiagnosisAndNotificationRepeater
    - BETSAYUSHReferralRepeater
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('repeater_id')
        parser.add_argument('filename')

    def handle(self, domain, repeater_id, filename, **options):
        records = iter_repeat_records_by_domain(domain, repeater_id=repeater_id)
        record_count = get_repeat_record_count(domain, repeater_id=repeater_id)

        row_names = [
            'EventID',
            'EventOccurDate',
            'BeneficiaryUUID',
            'BeneficiaryType',
            'Location',
            'DTOLocation',
            'EpisodeID'
            'succeeded',    # Some records did succeed when we sent them.
                            # Include this so they don't re-pay people.
        ]

        errors = []
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(row_names)

            for record in with_progress_bar(records, length=record_count):
                try:
                    payload = json.loads(record.get_payload())['incentive_details'][0]
                except Exception as e:
                    errors.append([record.payload_id, unicode(e)])
                    continue
                payload['succeeded'] = record.succeeded
                row = [payload.get(name) for name in row_names]
                writer.writerow(row)

        print "{} errors".format(len(errors))
        if len(errors) == 0:
            return

        with open('errors_{}'.format(filename), 'w') as f:
            writer = csv.writer(f)
            writer.write_row(['episode_id', 'error'])
            for error in errors:
                writer.write_row(errors)
