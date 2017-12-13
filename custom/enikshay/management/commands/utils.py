from __future__ import print_function

from __future__ import absolute_import
import csv
import datetime

from django.core.management import BaseCommand

from casexml.apps.case.mock import CaseFactory
from casexml.apps.case.xform import get_case_updates

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar

from custom.enikshay.case_utils import (
    get_person_case
)
from custom.enikshay.exceptions import ENikshayCaseNotFound
from custom.enikshay.const import ENROLLED_IN_PRIVATE


def get_result_recorded_form(test):
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


def get_test_created_form(test):
    return test.actions[0].form.form_data


def get_form_path(path, form_data):
    block = form_data
    while path:
        block = block.get(path[0], {})
        path = path[1:]
    return block


class BaseEnikshayCaseMigration(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('log_file_name')
        parser.add_argument('case_ids', nargs='*')
        parser.add_argument('--commit', action='store_true')

    def handle(self, domain, log_file_name, case_ids, **options):
        commit = options['commit']

        print("Starting {} migration on {} at {}".format(
            "real" if commit else "fake", domain, datetime.datetime.utcnow()
        ))

        accessor = CaseAccessors(domain)
        case_ids = case_ids or accessor.get_case_ids_in_domain(type=self.case_type)

        with open(log_file_name, "w") as log_file:
            writer = csv.writer(log_file)
            writer.writerow(
                ['case_id']
                + ['current_' + case_prop for case_prop in self.case_properties_to_update]
                + self.case_properties_to_update
                + [self.datamigration_case_property]
            )
            for case_id in with_progress_bar(case_ids):
                if self.is_valid_case(domain, case_id):
                    case = accessor.get_case(case_id)
                    updated_case_properties = self.get_case_property_updates(case, domain)
                    needs_update = bool(updated_case_properties)
                    updated_case_properties[self.datamigration_case_property] = 'yes' if needs_update else 'no'
                    writer.writerow(
                        [case.case_id]
                        + [case.get_case_property(case_prop) or '' for case_prop in self.case_properties_to_update]
                        + [updated_case_properties.get(case_prop, '') for case_prop in (
                            self.case_properties_to_update + [self.datamigration_case_property])]
                    )
                    if needs_update and commit:
                        self.commit_updates(domain, case.case_id, updated_case_properties)

            print("Finished at {}".format(datetime.datetime.utcnow()))

    def is_valid_case(self, domain, case_id):
        try:
            person_case = get_person_case(domain, case_id)
            return (self.include_public_cases == self._is_person_public(domain, person_case)
                    and self.include_private_cases == self._is_person_private(domain, person_case))
        except ENikshayCaseNotFound:
            return False

    @staticmethod
    def _is_person_public(domain, person_case):
        return person_case.get_case_property(ENROLLED_IN_PRIVATE) != 'true'

    @staticmethod
    def _is_person_private(domain, person_case):
        return person_case.get_case_property(ENROLLED_IN_PRIVATE) == 'true'

    @staticmethod
    def commit_updates(domain, case_id, updated_case_properties):
        CaseFactory(domain).update_case(case_id, update=updated_case_properties)

    @property
    def case_type(self):
        raise NotImplementedError

    @property
    def include_private_cases(self):
        raise NotImplementedError

    @property
    def include_public_cases(self):
        raise NotImplementedError

    @property
    def case_properties_to_update(self):
        raise NotImplementedError

    @property
    def datamigration_case_property(self):
        raise NotImplementedError

    @staticmethod
    def get_case_property_updates(case, domain):
        raise NotImplementedError
