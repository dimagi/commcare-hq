import csv

from django.core.management import BaseCommand

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar

from custom.enikshay.case_utils import get_person_case
from custom.enikshay.exceptions import ENikshayCaseNotFound


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')
        parser.add_argument('log_file_name')
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--deletion_id', dest='deletion_id', default='case_without_person')

    def handle(self, domain, case_type, log_file_name, **options):
        commit = options['commit']
        deletion_id = options['deletion_id']

        with open(log_file_name, 'w') as log_file:
            logger = self.get_logger(log_file)
            for case_id in with_progress_bar(self.get_case_ids(domain, case_type)):
                if self.should_delete(domain, case_id):
                    self.delete_case(case_id, commit, deletion_id, domain, logger, case_type)

    @staticmethod
    def get_logger(log_file):
        logger = csv.writer(log_file)
        logger.writerow(['case_id', 'deletion_id', 'case_type'])
        return logger

    @staticmethod
    def get_case_ids(domain, case_type):
        return CaseAccessors(domain).get_case_ids_in_domain(type=case_type)

    @staticmethod
    def should_delete(domain, case_id):
        try:
            return not get_person_case(domain, case_id)
        except ENikshayCaseNotFound:
            return True

    @staticmethod
    def delete_case(case_id, commit, deletion_id, domain, logger, case_type):
        logger.writerow([case_id, deletion_id, case_type])
        if commit:
            CaseAccessors(domain).soft_delete_cases([case_id], deletion_id=deletion_id)
