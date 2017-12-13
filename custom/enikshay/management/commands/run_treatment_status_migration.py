from __future__ import absolute_import
from __future__ import print_function
import datetime
import csv

from corehq.apps.es import CaseSearchES
from django.core.management import BaseCommand
from casexml.apps.case.mock import CaseStructure, CaseFactory
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import get_person_case_from_episode
from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.exceptions import ENikshayCaseNotFound


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            help="The domain to migrate."
        )
        parser.add_argument(
            "log_path",
            help="Path to write the log to"
        )
        parser.add_argument(
            '--commit',
            action='store_true',
            help="actually modifies the cases. Without this flag, it's a dry run."
        )

    def handle(self, commit, domain, log_path, **options):
        commit = commit
        factory = CaseFactory(domain)
        headers = [
            'case_id',
            'current_treatment_initiated',
            'current_treatment_status',
            'current_diagnosing_facility_id',
            'current_treatment_initiating_facility_id',
            'updated_treatment_initiated',
            'updated_treatment_status',
            'datamigration_treatment_status_fix',
        ]

        print("Starting {} migration on {} at {}".format(
            "real" if commit else "fake", domain, datetime.datetime.utcnow()
        ))

        case_ids = [
            hit['_id'] for hit in (CaseSearchES()
                                   .domain(domain)
                                   .case_type("episode")
                                   .case_property_query("episode_type", "confirmed_tb", "must")
                                   .run().hits)
        ]

        with open(log_path, "w") as log_file:
            writer = csv.writer(log_file)
            writer.writerow(headers)

            for episode in CaseAccessors(domain=domain).iter_cases(case_ids):
                if episode.get_case_property('datamigration_treatment_status_fix') != 'yes' \
                        and episode.get_case_property('diagnosing_facility_id') \
                        and episode.get_case_property('treatment_initiating_facility_id'):

                    #Filter and skip private cases
                    try:
                        person = get_person_case_from_episode(domain, episode.case_id)
                    except ENikshayCaseNotFound:
                        continue
                    if person.get_case_property(ENROLLED_IN_PRIVATE) != 'true':
                        current_treatment_initiated = episode.get_case_property('treatment_initiated')
                        current_treatment_status = episode.get_case_property('treatment_status')
                        current_diagnosing_facility_id = episode.get_case_property('diagnosing_facility_id')
                        current_treatment_initiating_facility_id = \
                            episode.get_case_property('treatment_initiating_facility_id')

                        if current_treatment_status == "initiated_outside_rntcp" \
                                or current_treatment_initiated == "yes_private":
                            # this should ideally not need a migration but checking anyway
                            treatment_initiated = "yes_private"
                            treatment_status = "initiated_outside_rntcp"
                        elif current_diagnosing_facility_id == current_treatment_initiating_facility_id:
                            treatment_initiated = "yes_phi"
                            treatment_status = "initiated_first_line_treatment"
                        else:
                            treatment_initiated = "yes_phi"
                            treatment_status = "initiated_outside_facility"

                        if treatment_initiated == current_treatment_initiated \
                                and treatment_status == current_treatment_status:
                            # skip
                            writer.writerow([episode.case_id,
                                             current_treatment_initiated,
                                             current_treatment_status,
                                             current_diagnosing_facility_id,
                                             current_treatment_initiating_facility_id,
                                             None,
                                             None,
                                             "no"])
                        else:
                            writer.writerow([episode.case_id,
                                             current_treatment_initiated,
                                             current_treatment_status,
                                             current_diagnosing_facility_id,
                                             current_treatment_initiating_facility_id,
                                             treatment_initiated,
                                             treatment_status,
                                             "yes"])

                            print('Updating {}...'.format(episode.case_id))
                            case_structure = CaseStructure(
                                case_id=episode.case_id,
                                walk_related=False,
                                attrs={
                                    "create": False,
                                    "update": {
                                        "datamigration_treatment_status_fix": "yes",
                                        "treatment_initiated": treatment_initiated,
                                        "treatment_status": treatment_status,
                                    },
                                },
                            )
                            if commit:
                                factory.create_or_update_case(case_structure)
        print("Migration finished at {}".format(datetime.datetime.utcnow()))
