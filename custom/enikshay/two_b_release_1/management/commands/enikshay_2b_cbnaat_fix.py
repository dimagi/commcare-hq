from __future__ import absolute_import
import datetime
import logging

from corehq.apps.es import CaseSearchES
from django.core.management import BaseCommand
from casexml.apps.case.mock import CaseStructure, CaseFactory
from casexml.apps.case.xform import get_case_updates
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

logger = logging.getLogger('enikshay_2b_cbnaat_fix')


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

    @staticmethod
    def _get_result_recorded_form(test):
        """get last form that set result_recorded to yes"""
        for action in reversed(test.actions):
            for update in get_case_updates(action.form):
                if (
                    update.id == test.case_id
                    and update.get_update_action()
                    and update.get_update_action().dynamic_properties.get('result_recorded') == 'yes'
                ):
                    return action.form.form_data

    @staticmethod
    def _get_path(path, form_data):
        block = form_data
        while path:
            block = block.get(path[0], {})
            path = path[1:]
        return block

    def handle(self, domain, log_path, **options):
        commit = options['commit']
        factory = CaseFactory(domain)

        logger.info("Starting {} migration on {} at {}".format(
            "real" if commit else "fake", domain, datetime.datetime.utcnow()
        ))

        cases = (CaseSearchES()
                 .domain(domain)
                 .case_type("test")
                 .case_property_query("test_type_value", "cbnaat", "must")
                 .values_list('case_id', flat=True))

        with open(log_path, "w") as f:
            for test in CaseAccessors(domain=domain).iter_cases(cases):
                updated_by_migration = test.get_case_property('updated_by_migration')
                if ((updated_by_migration == 'enikshay_2b_case_properties' or
                     updated_by_migration == 'enikshay_2b_reason_for_test_fix')
                        and test.get_case_property('result_recorded') == 'yes'):

                    drug_resistance_list = ''
                    drug_sensitive_list = ''
                    resistance_display = None

                    form_data = self._get_result_recorded_form(test)
                    sample_a = self._get_path(
                        'update_test_result cbnaat ql_sample_a sample_a_rif_resistance_result'.split(),
                        form_data,
                    )
                    sample_b = self._get_path(
                        'update_test_result cbnaat ql_sample_b sample_b_rif_resistance_result'.split(),
                        form_data,
                    )
                    if sample_a == 'detected' or sample_b == 'detected':
                        detected = 'TB Detected'
                        drug_resistance_list = 'r'
                        resistance_display = 'R: Res'
                    elif sample_a == 'not_detected' or sample_b == 'not_detected':
                        detected = 'TB Not Detected'
                        drug_sensitive_list = 'r'
                    else:
                        detected = ''

                    result_summary_display = '\n'.join([_f for _f in [
                        detected,
                        resistance_display,
                    ] if _f])

                    case_id = test.case_id
                    f.write(case_id + "\n")
                    logger.info(case_id)

                    case_structure = CaseStructure(
                        case_id=case_id,
                        walk_related=False,
                        attrs={
                            "create": False,
                            "update": {
                                "updated_by_migration": "enikshay_2b_cbnaat_fix",
                                "drug_resistance_list": drug_resistance_list,
                                "drug_sensitive_list": drug_sensitive_list,
                                "result_summary_display": result_summary_display,
                            },
                        },
                    )

                    if commit:
                        factory.create_or_update_case(case_structure)
        logger.info("Migration finished at {}".format(datetime.datetime.utcnow()))
