from __future__ import absolute_import
from __future__ import print_function
from django.core.management import BaseCommand

from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.locations.tasks import make_location_user
from corehq.apps.users.models import CommCareUser, UserRole
from custom.enikshay.private_sector_datamigration.models import Agency, UserDetail

from dimagi.utils.decorators.memoized import memoized


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('state_code')
        parser.add_argument('district_code')
        parser.add_argument('parent_loc_id')
        parser.add_argument('user_level', choices=['dev', 'real', 'test'])
        parser.add_argument('org_id', type=int)
        parser.add_argument('--sub_org_ids', metavar='sub_org_id', nargs='*', type=int)

    def handle(self, domain, state_code, district_code, parent_loc_id, user_level, org_id, **options):
        sub_org_ids = options['sub_org_ids'] or [0]
        dto_parent = SQLLocation.active_objects.get(location_id=parent_loc_id)
        for sub_org_id in sub_org_ids:
            dto = self.create_dto(domain, state_code, district_code, dto_parent, org_id, sub_org_id)
            for i, agency in enumerate(
                self.get_agencies_by_state_district_org(state_code, district_code, org_id, sub_org_id)
            ):
                print('handling agency %d...' % i)
                if agency.location_type is not None:
                    agency_loc = self.create_agency(domain, agency, dto, org_id, sub_org_id)
                    self.create_user(agency, agency_loc, user_level)

    def create_dto(self, domain, state_code, district_code, dto_parent, org_id, sub_org_id):
        orgaisation_id = sub_org_id or org_id
        return SQLLocation.objects.create(
            domain=domain,
            name=self._get_org_name_by_id(orgaisation_id),
            site_code='%s_%s_%d' % (state_code, district_code, orgaisation_id),
            location_type=LocationType.objects.get(
                domain=domain,
                code='dto',
            ),
            parent=dto_parent,
            metadata={
                'enikshay_enabled': 'yes',
                'is_test': 'no',
                'private_sector_org_id': str(orgaisation_id),
                'sector': 'private',
            },
        )

    @staticmethod
    def get_agencies_by_state_district_org(state_code, district_code, org_id, sub_org_id):
        agency_ids = UserDetail.objects.filter(
            isPrimary=True,
        ).filter(
            districtId=district_code,
            organisationId=org_id,
            subOrganisationId=sub_org_id,
            stateId=state_code,
        ).values('agencyId').distinct()
        return Agency.objects.filter(agencyId__in=agency_ids).order_by('agencyId')

    def create_agency(self, domain, agency, dto, org_id, sub_org_id):
        organisation_id = sub_org_id or org_id
        return SQLLocation.objects.create(
            domain=domain,
            name=agency.agencyName,
            site_code=str(agency.agencyId),
            location_type=self.get_location_type_by_domain_and_code(domain, agency.location_type),
            parent=dto,
            metadata={
                'enikshay_enabled': 'yes',
                'is_test': 'no',
                'nikshay_code': agency.nikshayId,
                'private_sector_agency_id': str(agency.agencyId),
                'private_sector_org_id': str(organisation_id),
                'sector': 'private',
            },
        )

    def create_user(self, agency, agency_loc, user_level):
        assert agency_loc.location_type.has_user

        agency_loc_id = agency_loc.location_id
        domain = agency_loc.domain

        user = CommCareUser.get_by_username('%s@%s.commcarehq.org' % (agency_loc.site_code, agency_loc.domain))
        if user is None:
            user = make_location_user(agency_loc)
        user.user_location_id = agency_loc_id
        user.set_location(agency_loc, commit=False)
        user.user_data['agency_id_legacy'] = agency_loc.metadata['private_sector_agency_id']
        user.set_role(
            domain,
            UserRole.by_domain_and_name(domain, 'Default Mobile Worker')[0].get_qualified_id()
        )
        user.user_data['user_level'] = user_level
        user.user_data['usertype'] = agency.usertype
        user.save()

        agency_loc.user_id = user._id
        agency_loc.save()

    @staticmethod
    def _get_org_name_by_id(org_id):
        return {
            1: 'PATH',
            2: 'MJK',
            3: 'Alert-India',
            4: 'WHP',
            5: 'DTO-Mehsana',
            6: 'Vertex',
            7: 'Accenture',
            8: 'BMGF',
            9: 'EY',
            10: 'CTD',
            11: 'Nagpur',
            12: 'Nagpur-rural',
            13: 'Nagpur_Corp',
            14: 'Surat',
            15: 'SMC',
            16: 'Surat_Rural',
            17: 'Rajkot',
        }[org_id]

    @staticmethod
    def get_user_name_for_agency(agency):
        return UserDetail.objects.get(
            isPrimary=True,
            agencyId=agency.agencyId,
        ).motechUserName

    @memoized
    def get_location_type_by_domain_and_code(self, domain, location_type_code):
        return LocationType.objects.get(
            domain=domain,
            code=location_type_code,
        )
