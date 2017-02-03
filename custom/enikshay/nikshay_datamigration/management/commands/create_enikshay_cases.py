import logging

from django.core.management import BaseCommand
import mock
from casexml.apps.case.mock import CaseFactory
from casexml.apps.phone.cleanliness import set_cleanliness_flags_for_domain

from custom.enikshay.nikshay_datamigration.factory import EnikshayCaseFactory, get_nikshay_codes_to_location
from custom.enikshay.nikshay_datamigration.models import PatientDetail

logger = logging.getLogger('nikshay_datamigration')

DEFAULT_NUMBER_OF_PATIENTS_PER_FORM = 50


def mock_ownership_cleanliness_checks():
    # this function is expensive so bypass this during processing
    return mock.patch(
        'casexml.apps.case.xform._get_all_dirtiness_flags_from_cases',
        new=lambda case_db, touched_cases: [],
    )


class Command(BaseCommand):

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
        parser.add_argument(
            '--chunksize',
            dest='chunk_size',
            default=DEFAULT_NUMBER_OF_PATIENTS_PER_FORM,
            type=int,
        )
        parser.add_argument(
            '--test-phi',
            dest='test_phi',
            default=None,
            type=str,
        )
        parser.add_argument(
            '--startswith',
            dest='startswith',
            default='',
            type=str,
        )

    @mock_ownership_cleanliness_checks()
    def handle(self, domain, **options):
        base_query = PatientDetail.objects.filter(
            PregId__startswith=options['startswith'],
        ).order_by('PregId')

        start = options['start']
        limit = options['limit']
        chunk_size = options['chunk_size']
        test_phi = options['test_phi']
        if test_phi:
            logger.warning("** USING TEST PHI ID **")

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
        factory = CaseFactory(domain=domain)
        case_structures = []

        for patient_detail in patient_details:
            counter += 1
            try:
                case_factory = EnikshayCaseFactory(
                    domain, patient_detail, nikshay_codes_to_location, test_phi
                )
                case_structures.extend(case_factory.get_case_structures_to_create())
            except Exception:
                num_failed += 1
                logger.error(
                    'Failed on %d of %d. Nikshay ID=%s' % (
                        counter, total, patient_detail.PregId
                    ),
                    exc_info=True,
                )
            else:
                num_succeeded += 1
                if num_succeeded % chunk_size == 0:
                    logger.info('committing cases {}-{}...'.format(num_succeeded - chunk_size, num_succeeded))
                    factory.create_or_update_cases(case_structures)
                    case_structures = []
                    logger.info('done')

                logger.info(
                    'Succeeded on %s of %d. Nikshay ID=%s' % (
                        counter, total, patient_detail.PregId
                    )
                )

        if case_structures:
            logger.info('committing final cases...'.format(num_succeeded - chunk_size, num_succeeded))
            factory.create_or_update_cases(case_structures)

        logger.info('Done creating cases for domain %s.' % domain)
        logger.info('Number of attempts: %d.' % counter)
        logger.info('Number of successes: %d.' % num_succeeded)
        logger.info('Number of failures: %d.' % num_failed)

        # since we circumvented cleanliness checks just call this at the end
        logger.info('Setting cleanliness flags')
        set_cleanliness_flags_for_domain(domain, force_full=True)
        logger.info('Done!')
