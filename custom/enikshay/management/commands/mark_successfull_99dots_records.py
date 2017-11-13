from __future__ import absolute_import, print_function

import csv
from datetime import datetime

from django.core.management.base import BaseCommand

from corehq.apps.hqcase.utils import update_case
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.repeaters.dbaccessors import (get_repeat_record_count,
                                                 iter_repeat_records_by_domain)
from corehq.motech.repeaters.models import RepeatRecord
from corehq.util.log import with_progress_bar
from custom.enikshay.case_utils import (get_adherence_cases_from_episode,
                                        get_person_case_from_episode)


class Command(BaseCommand):
    """Finds all records that were originally marked as failed due to a 99DOTS API
    error, but then were subsequently marked as successful. Sends all other
    pertinent records for these cases to 99DOTS.

    """
    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--commit', action='store_true')

    def handle(self, domain, **options):
        # For all successful registration records
        # If any have an attempt that id "A patient with this beneficiary_id already exists"
        # Check the episode case. If this doesn't have "dots_99_registered" then set this property to "true"
        self.commit = options['commit']
        repeater_id = 'dc73c3da43d42acd964d80b287926833'  # 99dots register
        accessor = CaseAccessors(domain)
        existing_message = "A patient with this beneficiary_id already exists"
        count = get_repeat_record_count(domain, repeater_id, state="SUCCESS")
        records = iter_repeat_records_by_domain(domain, repeater_id, state="SUCCESS")

        cases_to_update = set()
        print("Filtering successful cases")
        for repeat_record in with_progress_bar(records, length=count):
            if any((existing_message in attempt.message if attempt.message is not None else "")
                   for attempt in repeat_record.attempts):
                try:
                    episode = accessor.get_case(repeat_record.payload_id)
                except CaseNotFound:
                    continue
                if episode.get_case_property('dots_99_registered') != 'true':
                    cases_to_update.add(episode)

        timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")
        with open('{}_set_99dots_to_registered.csv'.format(timestamp), 'w') as f:
            writer = csv.writer(f)
            writer.writerow([
                'beneficiary_id',
                'episode_id',
                'UpdatePatient Status',
                'Adherence Status',
                'TreatmentOutcome Status'
            ])
            print("Updating {} successful cases in 99DOTS".format(len(cases_to_update)))
            for case in with_progress_bar(cases_to_update):
                writer.writerow([
                    get_person_case_from_episode(domain, case.case_id).case_id,
                    case.case_id,
                    self.update_registered_status(domain, case),
                    self.update_patients(domain, case),
                    self.send_adherence(domain, case),
                    self.send_treatment_outcome(domain, case),
                ])

    def update_registered_status(self, domain, case):
        try:
            if self.commit:
                update_case(domain, case.case_id, {'dots_99_registered': 'true'})
            return "dots_99_registered updated in eNikshay"
        except Exception as e:
            return "failure updating case in enikshay: {}".format(e)

    def update_patients(self, domain, case):
        repeater_id = 'b4e19fd859f852871703e8e32a1764a9'
        repeater_type = 'NinetyNineDotsUpdatePatientRepeater'
        return self.send_repeat_record(domain, case.case_id, repeater_id, repeater_type)

    def send_adherence(self, domain, case):
        repeater_id = '9cf9a0e2df49b6271573afe677725dc2'
        repeater_type = 'NinetyNineDotsAdherenceRepeater'

        adherence_cases = get_adherence_cases_from_episode(domain, case.case_id)
        if adherence_cases:
            return {
                adherence_case.case_id: self.send_repeat_record(domain, adherence_case.case_id, repeater_id, repeater_type)
                for adherence_case in adherence_cases
            }
        else:
            return "No Adherence Cases"

    def send_treatment_outcome(self, domain, case):
        repeater_id = '3d912c5d00c73e9de5eb6a11c52a7301'
        repeater_type = 'NinetyNineDotsTreatmentOutcomeRepeater'
        if case.dynamic_case_properties().get('treatment_outcome', '') != '':
            return self.send_repeat_record(domain, case.case_id, repeater_id, repeater_type)
        else:
            return "No Treatment Outcome"

    def send_repeat_record(self, domain, case_id, repeater_id, repeater_type):
        repeat_record = RepeatRecord(
            repeater_id=repeater_id,
            repeater_type=repeater_type,
            domain=domain,
            next_check=datetime.utcnow(),
            payload_id=case_id
        )

        if self.commit:
            repeat_record.fire()

        return repeat_record.state
