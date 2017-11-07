from __future__ import absolute_import
import datetime
import logging

from corehq.apps.es import CaseSearchES
from django.core.management import BaseCommand
from casexml.apps.case.mock import CaseStructure, CaseFactory

logger = logging.getLogger('enikshay_2b_referred_by_id_fix')


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
                 .case_property_query("case_version", "20", "must")
                 .scroll())

        with open(log_path, "w") as f:
            for case in cases:
                case_props = {prop['key']: prop['value'] for prop in case['case_properties']}
                referred_by_id = case_props.get('referred_by_id')
                updated_by_migration = case_props.get('updated_by_migration')
                if ((updated_by_migration == 'enikshay_2b_case_properties' or
                     updated_by_migration == 'enikshay_2b_treatment_status_fix')
                        and referred_by_id):

                    case_id = case['_id']
                    f.write(case_id + "\n")
                    logger.info(case_id)

                    case_structure = CaseStructure(
                        case_id=case_id,
                        walk_related=False,
                        attrs={
                            "create": False,
                            "update": {
                                "referred_outside_enikshay_by_id": referred_by_id,
                                "updated_by_migration": "enikshay_2b_referred_by_id_fix",
                            },
                        },
                    )

                    if commit:
                        factory.create_or_update_case(case_structure)
        logger.info("Migration finished at {}".format(datetime.datetime.utcnow()))
