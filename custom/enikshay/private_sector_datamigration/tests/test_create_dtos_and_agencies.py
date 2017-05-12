from datetime import datetime

from django.core.management import call_command
from django.test import TestCase

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from custom.enikshay.private_sector_datamigration.models import Agency, UserDetail
from custom.enikshay.tests.utils import ENikshayLocationStructureMixin


class TestCreateDTOsAndAgencies(ENikshayLocationStructureMixin, TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = 'test_domain'
        super(TestCreateDTOsAndAgencies, cls).setUpClass()

    def test_create_dtos(self):
        start_loc_count = SQLLocation.objects.filter(domain=self.domain).count()

        call_command('create_dtos_and_agencies', self.domain, '154', '189', self.sto.location_id, 'test', 1, 4)

        self.assertEqual(SQLLocation.objects.filter(domain=self.domain).count(), start_loc_count + 2)

        [dto_whp, dto_path] = SQLLocation.objects.filter(domain=self.domain).order_by('-last_modified')[:2]

        self.assertEqual(dto_path.location_type.code, 'dto')
        self.assertEqual(dto_path.name, 'PATH')
        self.assertEqual(dto_path.parent, self.sto)
        self.assertEqual(dto_path.site_code, '154_189_1')
        self.assertDictEqual(
            dto_path.metadata,
            {
                'enikshay_enabled': 'yes',
                'is_test': 'no',
                'private_sector_org_id': 1,
            }
        )

        self.assertEqual(dto_whp.location_type.code, 'dto')
        self.assertEqual(dto_whp.name, 'WHP')
        self.assertEqual(dto_whp.parent, self.sto)
        self.assertEqual(dto_whp.site_code, '154_189_4')
        self.assertDictEqual(
            dto_whp.metadata,
            {
                'enikshay_enabled': 'yes',
                'is_test': 'no',
                'private_sector_org_id': 4,
            }
        )

    def test_create_agencies(self):
        start_loc_count = SQLLocation.objects.filter(domain=self.domain).count()

        agency_id = 100789

        UserDetail.objects.create(
            id=1,
            agencyId=agency_id,
            districtId='189',
            isPrimary=True,
            motechUserName='org123',
            organisationId=1,
            passwordResetFlag=False,
            pincode=3,
            stateId='154',
            subOrganisationId=4,
            userId=5,
            valid=True,
        )
        Agency.objects.create(
            id=1,
            agencyId=agency_id,
            agencyName='Nicks Agency',
            agencyTypeId='ATPR',
            creationDate=datetime(2017, 5, 1),
            dateOfRegn=datetime(2017, 5, 1),
            modificationDate=datetime(2017, 5, 1),
            nikshayId='988765',
            organisationId=2,
            parentAgencyId=3,
            subOrganisationId=4,
        )

        call_command('create_dtos_and_agencies', self.domain, '154', '189', self.sto.location_id, 'dev', 1)

        self.assertEqual(SQLLocation.objects.filter(domain=self.domain).count(), start_loc_count + 2)

        [agency, dto] = SQLLocation.objects.filter(domain=self.domain).order_by('-last_modified')[:2]

        self.assertEqual(agency.location_type.code, 'pcp')
        self.assertEqual(agency.name, 'Nicks Agency')
        self.assertEqual(agency.parent, dto)
        self.assertEqual(agency.site_code, '100789')
        self.assertDictEqual(
            agency.metadata,
            {
                'enikshay_enabled': 'yes',
                'is_test': 'no',
                'nikshay_code': '988765',
                'private_sector_agency_id': agency_id,
                'private_sector_org_id': 1,

            }
        )

        self.assertEqual(dto.location_type.code, 'dto')
        self.assertEqual(dto.name, 'PATH')
        self.assertEqual(dto.parent, self.sto)
        self.assertEqual(dto.site_code, '154_189_1')
        self.assertDictEqual(
            dto.metadata,
            {
                'enikshay_enabled': 'yes',
                'is_test': 'no',
                'private_sector_org_id': 1,
            }
        )

        users = CommCareUser.by_domain(self.domain)
        self.assertEqual(len(users), 1)
        user = users[0]
        self.assertEqual(user.username, '%d@%s.commcarehq.org' % (agency_id, self.domain))
        self.assertDictEqual(
            user.user_data,
            {
                'commcare_location_ids': agency.location_id,
                'commcare_project': self.domain,
                'user_level': 'dev',
                'usertype': 'pcp',
            }
        )
        self.assertListEqual(user.assigned_location_ids, [agency.location_id])
        self.assertEqual(user.location_id, agency.location_id)
        self.assertEqual(user.user_location_id, agency.location_id)
