import logging

from django.core.management import BaseCommand

from custom.enikshay.nikshay_datamigration.factory import EnikshayCaseFactory, get_nikshay_codes_to_location, \
    get_nikshay_ids_to_preexisting_nikshay_person_cases
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
        logger.info('Starting migration of %d patient cases on domain %s.' % (total, domain))
        nikshay_codes_to_location = get_nikshay_codes_to_location(domain)
        nikshay_ids_to_preexisting_nikshay_person_cases = get_nikshay_ids_to_preexisting_nikshay_person_cases(
            domain
        )
        episodes = []
        limit = 20
        from casexml.apps.case.mock import CaseFactory
        for patient_detail in patient_details:
            # patients.append(patient_detail)
            # if len(patients) == limit:

            # counter += 1
            try:
                case_factory = EnikshayCaseFactory(
                    domain, patient_detail, nikshay_codes_to_location,
                    nikshay_ids_to_preexisting_nikshay_person_cases
                )
                episodes.append(case_factory.get_episode_structure())
                # case_factory.create_cases()
            except:
                num_failed += 1
                logger.error(
                    'Failed on %d of %d. Nikshay ID=%s' % (
                        counter, total, patient_detail.PregId
                    ),
                    exc_info=True,
                )
            else:
                if len(episodes) == limit:
                    CaseFactory(domain).create_or_update_cases(episodes)
                num_succeeded += limit
                logger.info(
                    'Succeeded on %s of %d. Nikshay ID=%s' % (
                        counter, total, patient_detail.PregId
                    )
                )
                episodes = []
        logger.info('Done creating cases for domain %s.' % domain)
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
