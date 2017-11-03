from __future__ import absolute_import
import csv
from datetime import datetime
from django.core.management.base import BaseCommand

from corehq.motech.repeaters.models import RepeatRecord
from corehq.apps.es import CaseSearchES

from custom.enikshay.case_utils import get_open_episode_case_from_person
from custom.enikshay.exceptions import ENikshayCaseNotFound


class Command(BaseCommand):
    """Sends secondary phone numbers to 99DOTS for those cases that have this property set
    """
    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--commit', action='store_true')

    def handle(self, domain, **options):
        repeater_id = 'b4e19fd859f852871703e8e32a1764a9'  # 99dots update
        repeater_type = 'NinetyNineDotsUpdatePatientRepeater'  # 99dots update

        cs = (
            CaseSearchES().domain(domain)
            .regexp_case_property_query('secondary_phone', '[0-9]+')
            .case_type('person')
            .case_property_query('enrolled_in_private', 'true')
        )
        person_case_ids = cs.values_list('_id', flat=True)

        enabled_ids = set()
        for person_id in person_case_ids:
            try:
                episode_case = get_open_episode_case_from_person('enikshay', person_id)
                if episode_case.get_case_property('dots_99_enabled') == 'true':
                    enabled_ids.add(person_id)
            except ENikshayCaseNotFound:
                pass

        with open('99dots_phone.csv', 'w') as f:
            writer = csv.writer(f)
            writer.writerow([
                'payload_id', 'state', 'payload', 'attempt message'
            ])
            for payload_id in enabled_ids:
                repeat_record = RepeatRecord(
                    repeater_id=repeater_id,
                    repeater_type=repeater_type,
                    domain=domain,
                    next_check=datetime.utcnow(),
                    payload_id=payload_id
                )

                if options['commit']:
                    repeat_record.fire()

                writer.writerow([
                    repeat_record.payload_id,
                    repeat_record.state,
                    repeat_record.get_payload(),
                    repeat_record.attempts[-1].message,
                ])
