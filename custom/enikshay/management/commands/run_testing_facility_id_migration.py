from __future__ import absolute_import
from __future__ import print_function
import datetime
import csv

from corehq.apps.es import CaseSearchES
from django.core.management import BaseCommand
from casexml.apps.case.mock import CaseStructure, CaseFactory
from casexml.apps.case.xform import get_case_updates
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


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
            if action.form is not None:
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

    def handle(self, commit, domain, log_path, **options):
        commit = commit
        factory = CaseFactory(domain)
        headers = [
            'case_id',
            'testing_facility_id',
            'datamigration_testing_facility_id',
        ]

        print("Starting {} migration on {} at {}".format(
            "real" if commit else "fake", domain, datetime.datetime.utcnow()
        ))

        case_ids = [
            hit['_id'] for hit in (CaseSearchES()
                                   .domain(domain)
                                   .case_type("test")
                                   .case_property_query("result_recorded", "yes", "must")
                                   .run().hits)
        ]

        failed_tests = []

        with open(log_path, "w") as log_file:
            writer = csv.writer(log_file)
            writer.writerow(headers)

            for test in CaseAccessors(domain=domain).iter_cases(case_ids):
                try:
                    if test.get_case_property('datamigration_testing_facility_id') != 'yes' \
                            and not test.get_case_property('testing_facility_id'):

                        form_data = self._get_result_recorded_form(test)
                        microscopy_id = self._get_path(
                            ['update_test_result',
                             'microscopy',
                             'ql_testing_facility_details',
                             'default_dmc_id'],
                            form_data
                        )
                        cbnaat_id = self._get_path(
                            ['update_test_result',
                             'cbnaat',
                             'ql_testing_facility_details',
                             'default_cdst_id'],
                            form_data
                        )
                        testing_facility_id = microscopy_id or cbnaat_id

                        if testing_facility_id:
                            writer.writerow([test.case_id, testing_facility_id, "yes"])
                            print('Updating {}...'.format(test.case_id))
                            case_structure = CaseStructure(
                                case_id=test.case_id,
                                walk_related=False,
                                attrs={
                                    "create": False,
                                    "update": {
                                        "datamigration_testing_facility_id": "yes",
                                        "testing_facility_id": testing_facility_id,
                                    },
                                },
                            )
                            if commit:
                                factory.create_or_update_case(case_structure)
                        else:
                            writer.writerow([test.case_id, testing_facility_id, "no"])
                except:
                    failed_tests.append(test.case_id)
        print("Migration finished at {}".format(datetime.datetime.utcnow()))
        print("Failed tests: {}".format(failed_tests))
