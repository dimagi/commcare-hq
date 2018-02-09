from __future__ import absolute_import
from datetime import date
import logging
import mock

from django.core.management import (
    BaseCommand,
    CommandError,
)
from django.db.models import Q

from casexml.apps.case.mock import CaseFactory
from casexml.apps.phone.cleanliness import set_cleanliness_flags_for_domain

from corehq.apps.locations.models import SQLLocation
from custom.enikshay.private_sector_datamigration.factory import BeneficiaryCaseFactory
from custom.enikshay.private_sector_datamigration.models import (
    Agency,
    Beneficiary,
    Beneficiary_Jul7,
    Episode,
    UserDetail,
)

logger = logging.getLogger('private_sector_datamigration')

DEFAULT_NUMBER_OF_PATIENTS_PER_FORM = 1


def mock_ownership_cleanliness_checks():
    # this function is expensive so bypass this during processing
    return mock.patch(
        'casexml.apps.case.xform._get_all_dirtiness_flags_from_cases',
        new=lambda case_db, touched_cases: [],
    )


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('migration_comment')
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
            '--default-location-owner-id',
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
        parser.add_argument(
            '--owner-suborganisation-ids',
            default=None,
            metavar='owner_suborganisation_id',
            nargs='+',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            dest='dry_run',
        )
        parser.add_argument(
            '--incremental-migration',
            action='store_true',
            default=False,
            dest='incremental_migration',
        )
        parser.add_argument(
            '--beneficiary-org-id',
            default=None,
            type=int,
        )
        parser.add_argument(
            '--beneficiary-suborg-id',
            default=None,
            type=int,
        )

    @mock_ownership_cleanliness_checks()
    def handle(self, domain, migration_comment, **options):
        case_ids = options['caseIds']
        chunk_size = options['chunk_size']
        limit = options['limit']
        owner_district_id = options['owner_district_id']
        owner_organisation_ids = options['owner_organisation_ids']
        owner_suborganisation_ids = options['owner_suborganisation_ids']
        owner_state_id = options['owner_state_id']
        skip_adherence = options['skip_adherence']
        start = options['start']

        logger.info('domain=%s' % domain)
        logger.info('migration_comment=%s' % migration_comment)
        for arg in [
            'caseIds',
            'chunk_size',
            'limit',
            'owner_district_id',
            'owner_organisation_ids',
            'owner_suborganisation_ids',
            'owner_state_id',
            'skip_adherence',
            'start',
            'default_location_owner_id',
            'location_owner_id',
            'dry_run',
            'incremental_migration',
            'beneficiary_org_id',
            'beneficiary_suborg_id',
        ]:
            logger.info('%s=%s' % (arg, str(options[arg])))

        default_location_owner_id = options['default_location_owner_id']
        if default_location_owner_id:
            default_location_owner = SQLLocation.objects.get(
                domain=domain,
                location_id=default_location_owner_id,
            )
        else:
            default_location_owner = None

        location_owner_id = options['location_owner_id']
        if location_owner_id:
            location_owner = SQLLocation.objects.get(
                domain=domain,
                location_id=location_owner_id,
            )
        else:
            location_owner = None

        if case_ids and owner_state_id:
            raise CommandError('Cannot specify both caseIds and owner-state-id')
        if not owner_state_id and owner_district_id:
            raise CommandError('Cannot specify owner-district-id without owner-state-id')
        if not owner_organisation_ids and owner_suborganisation_ids:
            raise CommandError('Cannot specify owner-suborganisation-ids without owner-organisation-ids')

        beneficiaries = get_beneficiaries(
            start, limit, case_ids, owner_state_id, owner_district_id,
            owner_organisation_ids, owner_suborganisation_ids,
            options['beneficiary_org_id'], options['beneficiary_suborg_id'],
            options['incremental_migration']
        )

        migrate_to_enikshay(
            domain, migration_comment, beneficiaries, skip_adherence, chunk_size,
            location_owner, default_location_owner, options['dry_run']
        )


def get_beneficiaries_in_date_range():
    new_episode_beneficiary_ids = Episode.objects.filter(
        creationDate__gte=date(2016, 1, 1),
    ).values('beneficiaryID')

    return Beneficiary.objects.filter(
        (
            Q(caseStatus='suspect')
            & Q(dateOfRegn__gte=date(2017, 1, 1))
        )
        | (
            Q(caseStatus__in=['patient', 'patient '])
            & (
                Q(caseId__in=new_episode_beneficiary_ids)
                | Q(dateOfRegn__gte=date(2016, 1, 1))
            )
        )
    ).order_by('caseId')


def get_beneficiaries(start, limit, case_ids, owner_state_id, owner_district_id,
                      owner_organisation_ids, owner_suborganisation_ids,
                      beneficiary_org_id, beneficiary_suborg_id, incremental_migration):
    beneficiaries_query = get_beneficiaries_in_date_range()

    if beneficiary_org_id is not None:
        beneficiaries_query = beneficiaries_query.filter(organisationId=beneficiary_org_id)

    if beneficiary_suborg_id is not None:
        beneficiaries_query = beneficiaries_query.filter(subOrganizationId=beneficiary_suborg_id)

    if case_ids:
        beneficiaries_query = beneficiaries_query.filter(caseId__in=case_ids)

    if owner_state_id or owner_district_id or owner_organisation_ids or owner_suborganisation_ids:
        user_details = UserDetail.objects.filter(isPrimary=True)

        if owner_state_id:
            user_details = user_details.filter(stateId=owner_state_id)

            if owner_district_id:
                user_details = user_details.filter(districtId=owner_district_id)

        if owner_organisation_ids:
            user_details = user_details.filter(organisationId__in=owner_organisation_ids)

        if owner_suborganisation_ids:
            user_details = user_details.filter(subOrganisationId__in=owner_suborganisation_ids)

        # Check that there is an actual agency object for the motech username
        agency_ids = Agency.objects.filter(agencyId__in=user_details.values('agencyId')).values('agencyId')
        motech_usernames = UserDetail.objects.filter(agencyId__in=agency_ids).values('motechUserName')

        bene_ids_treating = Episode.objects.filter(treatingQP__in=motech_usernames).values('beneficiaryID')
        bene_ids_treating_away = Episode.objects.exclude(treatingQP__in=motech_usernames).values('beneficiaryID')
        bene_ids_from_referred = Beneficiary.objects.filter(referredQP__in=motech_usernames).values('caseId')

        beneficiaries_query = beneficiaries_query.filter(
            Q(caseId__in=bene_ids_treating)
            | ((~Q(caseId__in=bene_ids_treating_away)) & Q(caseId__in=bene_ids_from_referred))
        )

    if incremental_migration:
        beneficiaries_query = beneficiaries_query.exclude(caseId__in=Beneficiary_Jul7.objects.values('caseId'))

    _assert_always_null(beneficiaries_query)

    if limit is not None:
        return beneficiaries_query[start:start + limit]
    else:
        return beneficiaries_query[start:]


def migrate_to_enikshay(domain, migration_comment, beneficiaries, skip_adherence, chunk_size,
                        location_owner, default_location_owner, dry_run):
    total = beneficiaries.count()
    counter = 0
    num_succeeded = 0
    num_failed = 0
    num_failed_chunks = 0
    logger.info('Starting migration of %d patients in domain %s.' % (total, domain))

    if dry_run:
        logger.info('Dry run, exiting...')
        return

    factory = CaseFactory(domain=domain)
    case_structures = []

    for beneficiary in beneficiaries:
        counter += 1
        try:
            case_factory = BeneficiaryCaseFactory(
                domain, migration_comment, beneficiary, location_owner, default_location_owner
            )
            case_structures.extend(case_factory.get_case_structures_to_create(skip_adherence))
        except Exception:
            num_failed += 1
            logger.error(
                'Failed on %d of %d. Case ID=%s' % (
                    counter, total, beneficiary.caseId
                ),
                exc_info=True,
            )
        else:
            num_succeeded += 1
            if num_succeeded % chunk_size == 0:
                logger.info('%d cases to save.' % len(case_structures))
                logger.info('committing beneficiaries {}-{}...'.format(
                    num_succeeded - chunk_size + 1, num_succeeded
                ))
                try:
                    factory.create_or_update_cases(case_structures)
                except Exception:
                    num_failed_chunks += 1
                    logger.error(
                        'Failure writing case structures',
                        exc_info=True,
                    )
                case_structures = []
                logger.info('done')

            logger.info(
                'Succeeded on %s of %d. Case ID=%s' % (
                    counter, total, beneficiary.caseId
                )
            )

    if case_structures:
        logger.info('committing final cases...'.format(num_succeeded - chunk_size, num_succeeded))
        factory.create_or_update_cases(case_structures)

    logger.info('Done creating cases for domain %s.' % domain)
    logger.info('Number of attempts: %d.' % counter)
    logger.info('Number of successes: %d.' % num_succeeded)
    logger.info('Number of failures: %d.' % num_failed)
    logger.info('Number of chunks to fail writing: %d' % num_failed_chunks)

    # since we circumvented cleanliness checks just call this at the end
    logger.info('Setting cleanliness flags')
    set_cleanliness_flags_for_domain(domain, force_full=True, raise_soft_assertions=False)
    logger.info('Done!')


def _assert_always_null(beneficiaries_query):
    assert not beneficiaries_query.filter(mdrTBSuspected__isnull=False).exists()
    assert not beneficiaries_query.filter(middleName__isnull=False).exists()
    assert not beneficiaries_query.filter(nikshayId__isnull=False).exists()
    assert not beneficiaries_query.filter(symptoms__isnull=False).exists()
    assert not beneficiaries_query.filter(tsType__isnull=False).exists()
    assert not Episode.objects.filter(phoneNumber__isnull=False).exists()
