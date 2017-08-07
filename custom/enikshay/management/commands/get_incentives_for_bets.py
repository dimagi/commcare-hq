import csv
import json

from django.core.management.base import BaseCommand

from corehq.util.log import with_progress_bar
from corehq.motech.repeaters.dbaccessors import iter_repeat_records_by_domain, get_repeat_record_count


class Command(BaseCommand):
    help = """
    Output 3 CSV files of incentive payloads that were sent to BETS in repeater <repeater_id>.
    The second file contains a list of duplicate episode ids which should be handled manually.
    The third file contains a list of errored cases.

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
        seen_incentive_ids = set()
        duplicate_incentive_ids = set()
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
                incentive_episode_pair = (payload.get('EpisodeID'), payload.get('EventID'),)
                if incentive_episode_pair in seen_incentive_ids:
                    duplicate_incentive_ids.add(incentive_episode_pair)
                else:
                    seen_incentive_ids.add(incentive_episode_pair)
                row = [payload.get(name) for name in row_names]

                writer.writerow(row)

        print "{} duplicates found".format(len(duplicate_incentive_ids))
        if duplicate_incentive_ids:
            with open('duplicates_{}'.format(filename), 'w') as f:
                writer = csv.writer(f)
                writer.write_row(['episode_id', 'event_id'])
                for duplicate_id in duplicate_incentive_ids:
                    writer.write_row(duplicate_id)

        print "{} errors".format(len(errors))
        if errors:
            with open('errors_{}'.format(filename), 'w') as f:
                writer = csv.writer(f)
                writer.write_row(['episode_id', 'error'])
                for error in errors:
                    writer.write_row(errors)
