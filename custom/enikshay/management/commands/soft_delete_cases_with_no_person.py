import csv

from django.core.management import BaseCommand

from dimagi.utils.chunked import chunked

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar

from custom.enikshay.case_utils import get_person_case
from custom.enikshay.exceptions import ENikshayCaseNotFound


MIGRATION_CASE_PROPERTIES = [
    'migration_created_case',
    'migration_comment',
    'migration_created_from_record',
]


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')
        parser.add_argument('log_file_name')
        parser.add_argument('case_ids', nargs='*')
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--deletion_id', dest='deletion_id', default='case_without_person')

    def handle(self, domain, case_type, log_file_name, case_ids, **options):
        commit = options['commit']
        deletion_id = options['deletion_id']

        if not case_ids:
            case_ids = self.get_case_ids(domain, case_type)

        with open(log_file_name, 'w') as log_file:
            logger = self.get_logger(log_file)
            for case_ids_to_delete in chunked(self.get_case_ids_to_delete(domain, case_ids), 100):
                case_ids_to_delete = list(case_ids_to_delete)
                self.delete_cases(case_ids_to_delete, commit, deletion_id, domain, logger, case_type)

    @staticmethod
    def get_logger(log_file):
        logger = csv.writer(log_file)
        logger.writerow(
            [
                'case_id', 'deletion_id', 'case_type',
                'date_form_created', 'date_form_modified',
                'date_form_modified_non_system', 'last_user_to_modify',
            ] + MIGRATION_CASE_PROPERTIES
        )
        return logger

    @staticmethod
    def get_case_ids(domain, case_type):
        return CaseAccessors(domain).get_case_ids_in_domain(type=case_type)

    @staticmethod
    def get_case_ids_to_delete(domain, case_ids):
        for case_id in with_progress_bar(case_ids):
            if _is_case_missing_person(domain, case_id):
                yield case_id

    @staticmethod
    def delete_cases(case_ids, commit, deletion_id, domain, logger, case_type):
        for case_id in case_ids:
            _log_case_to_delete(case_id, deletion_id, domain, logger, case_type)
        if commit:
            CaseAccessors(domain).soft_delete_cases(case_ids, deletion_id=deletion_id)


def _is_case_missing_person(domain, case_id):
    try:
        return not get_person_case(domain, case_id)
    except ENikshayCaseNotFound:
        return True


def _log_case_to_delete(case_id, deletion_id, domain, logger, case_type):
    date_form_modified_non_system = ''
    last_user_to_modify = ''

    case = CaseAccessors(domain).get_case(case_id)

    date_form_created = case.actions[0].form.received_on if case.actions[0].form is not None else ''
    date_form_modified = case.actions[-1].form.received_on if case.actions[-1].form is not None else ''

    for action in reversed(case.actions):
        form = action.form
        if form and form.user_id and form.user_id != 'system':
            last_user_to_modify = form.user_id
            date_form_modified_non_system = form.received_on
            break

    logger.writerow(
        [
            case_id, deletion_id, case_type,
            date_form_created, date_form_modified,
            date_form_modified_non_system, last_user_to_modify,
        ] + [(case.get_case_property(case_prop) or '') for case_prop in MIGRATION_CASE_PROPERTIES]
    )
