from django.core.management import BaseCommand

from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.locations.tasks import make_location_user
from custom.enikshay.private_sector_datamigration.models import Agency, UserDetail


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('state_code')
        parser.add_argument('district_code')
        parser.add_argument('parent_loc_id')
        parser.add_argument('user_level', choices=['dev', 'real', 'test'])
        parser.add_argument('org_ids', metavar='org_id', nargs='*', type=int)

    def handle(self, domain, state_code, district_code, parent_loc_id, user_level, org_ids, **options):
        dto_parent = SQLLocation.active_objects.get(location_id=parent_loc_id)
        for org_id in org_ids:
            dto = self.create_dto(domain, state_code, district_code, dto_parent, org_id)
            for agency in self.get_agencies_by_state_district_org(state_code, district_code, org_id):
                agency_loc = self.create_agency(domain, agency, dto, org_id)
                agency_user = make_location_user(agency_loc)
                agency_user.assigned_location_ids = [agency_loc.location_id]
                agency_user.location_id = agency_loc.location_id
                agency_user.user_data['commcare_location_id'] = agency_loc.location_id
                agency_user.user_data['user_level'] = user_level
                agency_user.user_data['usertype'] = self.get_usertype(agency_loc.location_type.code)
                agency_user.user_location_id = agency_loc.location_id
                agency_user.save()

    def create_dto(self, domain, state_code, district_code, dto_parent, org_id):
        return SQLLocation.objects.create(
            domain=domain,
            name=self._get_org_name_by_id(org_id),
            site_code='%s_%s_%d' % (state_code, district_code, org_id),
            location_type=LocationType.objects.get(
                domain=domain,
                code='dto',
            ),
            parent=dto_parent,
            metadata={
                'enikshay_enabled': 'yes',
                'is_test': 'no',
                'private_sector_org_id': org_id,
            },
        )

    @staticmethod
    def get_agencies_by_state_district_org(state_code, district_code, org_id):
        agency_ids = UserDetail.objects.filter(
            isPrimary=True,
        ).filter(
            districtId=district_code,
            organisationId=org_id,
            stateId=state_code,
        ).values('agencyId').distinct()
        return Agency.objects.filter(agencyId__in=agency_ids).order_by('agencyId')

    @staticmethod
    def create_agency(domain, agency, dto, org_id):
        return SQLLocation.objects.create(
            domain=domain,
            name=agency.agencyName,
            site_code=str(agency.agencyId),
            location_type=LocationType.objects.get(
                domain=domain,
                code=agency.location_type,
            ),
            parent=dto,
            metadata={
                'enikshay_enabled': 'yes',
                'is_test': 'no',
                'nikshay_code': agency.nikshayId,
                'private_sector_agency_id': agency.agencyId,
                'private_sector_org_id': org_id,

            },
        )

    @staticmethod
    def get_usertype(code):
        return {
            'pac': 'pac',
            'pcc': 'pcc-chemist',
            'pdr': 'deo',
            'pcp': 'pcp',
            'plc': 'plc',
        }[code]

    @staticmethod
    def _get_org_name_by_id(org_id):
        return {
            1: 'PATH',
            4: 'WHP',
            5: 'DTO-Mehsana',
        }[org_id]
