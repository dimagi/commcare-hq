import logging
from django.core.management.base import BaseCommand

from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.models import RebuildWithReason
from io import open


logger = logging.getLogger('rebuild_cases')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = ('Rebuild given cases')

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('cases_csv_file')

    def handle(self, domain, cases_csv_file, **options):
        cases = []
        with open(cases_csv_file, 'r') as f:
            lines = f.readlines()
            cases = [l.strip() for l in lines]

        rebuild_cases(domain, cases, logger)


def rebuild_cases(domain, cases, logger):
    detail = RebuildWithReason(reason='undo UUID clash')
    for case_id in cases:
        try:
            FormProcessorSQL.hard_rebuild_case(domain, case_id, detail)
            logger.info('Case %s rebuilt' % case_id)
        except:
            logger.error("Exception rebuilding case %s".format(case_id))
            logger.exception("message")
