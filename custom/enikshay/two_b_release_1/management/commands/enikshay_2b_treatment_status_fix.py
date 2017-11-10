from __future__ import absolute_import
import datetime
import logging

from corehq.apps.es import CaseSearchES
from django.core.management import BaseCommand
from casexml.apps.case.mock import CaseStructure, CaseFactory

from custom.enikshay.exceptions import NikshayLocationNotFound

logger = logging.getLogger('enikshay_2b_reason_for_test_fix')


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

    def handle(self, domain, log_path, **options):
        commit = options['commit']
        factory = CaseFactory(domain)

        logger.info("Starting {} migration on {} at {}".format(
            "real" if commit else "fake", domain, datetime.datetime.utcnow()
        ))

        cases = (CaseSearchES()
                 .domain(domain)
                 .case_type("episode")
                 .scroll())

        with open(log_path, "w") as f:
            for case in cases:
                case_props = {prop['key']: prop['value'] for prop in case['case_properties']}
                treatment_status = None
                treatment_initiated = case_props.get('treatment_initiated')
                diagnosing_facility_id = case_props.get('diagnosing_facility_id')
                treatment_initiating_facility_id = case_props.get('treatment_initiating_facility_id')

                if treatment_initiated == 'yes_phi' and \
                        diagnosing_facility_id and treatment_initiating_facility_id and \
                        diagnosing_facility_id != treatment_initiating_facility_id:
                    treatment_status = 'initiated_outside_facility'
                elif treatment_initiated == 'yes_phi' and \
                        diagnosing_facility_id and treatment_initiating_facility_id:
                    treatment_status = 'initiated_first_line_treatment'
                elif treatment_initiated == 'yes_private':
                    treatment_status = 'initiated_outside_rntcp'

                if treatment_status:
                    case_id = case['_id']
                    f.write(case_id + "\n")
                    logger.info(case_id)

                    case_structure = CaseStructure(
                        case_id=case_id,
                        walk_related=False,
                        attrs={
                            "create": False,
                            "update": {
                                "treatment_status": treatment_status,
                                "updated_by_migration": "enikshay_2b_treatment_status_fix",
                            },
                        },
                    )

                    if commit:
                        try:
                            factory.create_or_update_case(case_structure)
                        except NikshayLocationNotFound:
                            pass
        logger.info("Migration finished at {}".format(datetime.datetime.utcnow()))
