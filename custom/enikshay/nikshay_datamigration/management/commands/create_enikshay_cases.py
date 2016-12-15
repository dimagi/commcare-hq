import logging

from django.core.management import BaseCommand

from custom.enikshay.nikshay_datamigration.factory import EnikshayCaseFactory
from custom.enikshay.nikshay_datamigration.models import PatientDetail

logger = logging.getLogger('nikshay_datamigration')


class Command(BaseCommand):

    def handle(self, domain, **options):
        base_query = PatientDetail.objects.all()

        start = options['start']
        limit = options['limit']

        if limit is not None:
            patient_details = base_query[start:start + limit]
        else:
            patient_details = base_query[start:]

        total = patient_details.count()
        counter = 0
        num_succeeded = 0
        num_failed = 0
        logger.info('Starting migration of %d patient cases.' % total)
        for patient_detail in patient_details:
            counter += 1
            try:
                case_factory = EnikshayCaseFactory(domain, patient_detail)
                case_factory.create_cases()
            except:
                num_failed += 1
                logger.error(
                    'Failed on %d of %d. Nikshay ID=%s' % (
                        counter, total, patient_detail.PregId
                    ),
                    exc_info=True,
                )
            else:
                num_succeeded += 1
                logger.info(
                    'Succeeded on %s of %d. Nikshay ID=%s' % (
                        counter, total, patient_detail.PregId
                    )
                )
        logger.info('Done.')
        logger.info('Number of attempts: %d.' % counter)
        logger.info('Number of successes: %d.' % num_succeeded)
        logger.info('Number of failures: %d.' % num_failed)

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--start',
            dest='start',
            default=0,
            type=int,
        )
        parser.add_argument(
            '--limit',
            dest='limit',
            default=None,
            type=int,
        )
