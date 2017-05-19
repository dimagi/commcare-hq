import logging
import mock

from django.core.management import BaseCommand
from django.db.models import Q

from casexml.apps.case.mock import CaseFactory
from casexml.apps.phone.cleanliness import set_cleanliness_flags_for_domain

from corehq.apps.locations.models import SQLLocation
from custom.enikshay.private_sector_datamigration.factory import BeneficiaryCaseFactory
from custom.enikshay.private_sector_datamigration.models import (
    Adherence,
    Agency,
    Beneficiary,
    Episode,
    UserDetail,
)

logger = logging.getLogger('private_sector_datamigration')

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
            '--caseIds',
            dest='caseIds',
            default=None,
            metavar='caseId',
            nargs='+',
        )
        parser.add_argument(
            '--skip-adherence',
            action='store_true',
            default=False,
            dest='skip_adherence',
        )
        parser.add_argument(
            '--location-owner-id',
        )
        parser.add_argument(
            '--owner-state-id',
        )
        parser.add_argument(
            '--owner-district-id',
        )
        parser.add_argument(
            '--owner-organisation-ids',
            default=None,
            metavar='owner_organisation_id',
            nargs='+',
        )

    @mock_ownership_cleanliness_checks()
    def handle(self, domain, **options):
        assert not options['caseIds'] or not options['owner_state_id']
        assert options['owner_state_id'] or not options['owner_district_id']

        base_query = Beneficiary.objects.filter(
            caseStatus__in=['suspect', 'patient', 'patient '],
        )

        user_details = None

        if options['owner_state_id']:
            user_details = user_details or UserDetail.objects.filter(
                isPrimary=True
            )
            user_details = user_details.filter(
                stateId=options['owner_state_id'],
            )

            if options['owner_district_id']:
                user_details = user_details.filter(districtId=options['owner_district_id'])

        if options['owner_organisation_ids']:
            user_details = user_details or UserDetail.objects.filter(
                isPrimary=True
            )
            user_details = user_details.filter(organisationId__in=options['owner_organisation_ids'])

        if user_details:
            # Confirm that there is an actual agency object for the motech username
            agency_ids = Agency.objects.filter(agencyId__in=user_details.values('agencyId')).values('agencyId')
            motech_usernames = UserDetail.objects.filter(agencyId__in=agency_ids).values('motechUserName')

            bene_ids_treating = Episode.objects.filter(treatingQP__in=motech_usernames).values('beneficiaryID')
            bene_ids_treating_away = Episode.objects.exclude(treatingQP__in=motech_usernames).values('beneficiaryID')
            bene_ids_from_referred = Beneficiary.objects.filter(referredQP__in=motech_usernames).values('caseId')

            base_query = base_query.filter(
                Q(caseId__in=bene_ids_treating)
                | ((~Q(caseId__in=bene_ids_treating_away)) & Q(caseId__in=bene_ids_from_referred))
            )

        if options['caseIds']:
            base_query = base_query.filter(caseId__in=options['caseIds'])

        start = options['start']
        limit = options['limit']
        chunk_size = options['chunk_size']

        if limit is not None:
            beneficiaries = base_query[start:start + limit]
        else:
            beneficiaries = base_query[start:]

        location_owner_id = options['location_owner_id']
        if location_owner_id:
            location_owner = SQLLocation.objects.get(
                location_id=location_owner_id,
            )
        else:
            location_owner = None

        # Assert never null
        assert not beneficiaries.filter(firstName__isnull=True).exists()
        assert not beneficiaries.filter(lastName__isnull=True).exists()
        assert not beneficiaries.filter(phoneNumber__isnull=True).exists()
        assert not Episode.objects.filter(dateOfDiagnosis__isnull=True).exists()
        assert not Episode.objects.filter(patientWeight__isnull=True).exists()
        assert not Episode.objects.filter(rxStartDate__isnull=True).exists()
        assert not Episode.objects.filter(site__isnull=True).exists()
        assert not Adherence.objects.filter(creationDate__isnull=True).exists()

        # Assert always null
        assert not beneficiaries.filter(mdrTBSuspected__isnull=False).exists()
        assert not beneficiaries.filter(middleName__isnull=False).exists()
        assert not beneficiaries.filter(nikshayId__isnull=False).exists()
        assert not beneficiaries.filter(symptoms__isnull=False).exists()
        assert not beneficiaries.filter(tsType__isnull=False).exists()
        assert not Episode.objects.filter(phoneNumber__isnull=False).exists()

        total = beneficiaries.count()
        counter = 0
        num_succeeded = 0
        num_failed = 0
        logger.info('Starting migration of %d patients in domain %s.' % (total, domain))
        factory = CaseFactory(domain=domain)
        case_structures = []

        for beneficiary in beneficiaries:
            counter += 1
            try:
                case_factory = BeneficiaryCaseFactory(domain, beneficiary, location_owner)
                case_structures.extend(case_factory.get_case_structures_to_create(options['skip_adherence']))
            except Exception:
                num_failed += 1
                logger.error(
                    'Failed on %d of %d. Nikshay ID=%s' % (
                        counter, total, beneficiary.nikshayId
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
                        counter, total, beneficiary.nikshayId
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
        set_cleanliness_flags_for_domain(domain, force_full=True, raise_soft_assertions=False)
        logger.info('Done!')
