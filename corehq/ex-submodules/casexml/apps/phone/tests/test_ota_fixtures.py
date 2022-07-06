from django.test import TestCase
from corehq.blobs import get_blob_db
from casexml.apps.phone.utils import MockDevice
from corehq.apps.domain.models import Domain
from corehq.apps.fixtures.models import (
    FIXTURE_BUCKET,
    LookupTable,
    LookupTableRow,
    TypeField,
    Field,
)
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.tests.utils import sharded

DOMAIN = 'fixture-test'
SA_PROVINCES = 'sa_provinces'
FR_PROVINCES = 'fr_provinces'


@sharded
class OtaFixtureTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(OtaFixtureTest, cls).setUpClass()
        cls.domain = Domain.get_or_create_with_name(DOMAIN, is_active=True)
        cls.addClassCleanup(cls.domain.delete)
        cls.user = CommCareUser.create(DOMAIN, 'bob', 'mechanic', None, None)
        cls.addClassCleanup(cls.user.delete, None, None)
        cls.group1 = Group(domain=DOMAIN, name='group1', case_sharing=True, users=[cls.user._id])
        cls.group1.save()
        cls.group2 = Group(domain=DOMAIN, name='group2', case_sharing=True, users=[cls.user._id])
        cls.group2.save()

        cls.item_lists = {
            SA_PROVINCES: make_item_lists(SA_PROVINCES, 'western cape'),
            FR_PROVINCES: make_item_lists(FR_PROVINCES, 'burgundy'),
        }
        from corehq.apps.fixtures.dbaccessors import delete_all_fixture_data
        cls.addClassCleanup(delete_all_fixture_data, DOMAIN)
        cls.addClassCleanup(get_blob_db().delete, key=FIXTURE_BUCKET + "/" + DOMAIN)

        cls.restore_user = cls.user.to_ota_restore_user(DOMAIN)

    def test_skip_fixture(self):
        device = MockDevice(self.domain, self.restore_user)
        restore = device.sync().payload.decode('utf-8')
        self.assertIn('<fixture ', restore)
        restore_without_fixture = device.sync(skip_fixtures=True).payload.decode('utf-8')
        self.assertNotIn('<fixture ', restore_without_fixture)


def make_item_lists(tag, item_name):
    data_type = LookupTable(
        domain=DOMAIN,
        tag=tag,
        fields=[TypeField(name="name")],
        item_attributes=[],
        is_global=True
    )
    data_type.save()

    data_item = LookupTableRow(
        domain=DOMAIN,
        table_id=data_type.id,
        fields={"name": [Field(value=item_name)]},
        item_attributes={},
        sort_key=0,
    )
    data_item.save()
    return data_type, data_item
