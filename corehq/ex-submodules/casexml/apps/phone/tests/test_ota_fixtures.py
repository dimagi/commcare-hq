from django.test import TestCase
from corehq.blobs import get_blob_db
from casexml.apps.phone.utils import MockDevice
from corehq.apps.domain.models import Domain
from corehq.apps.fixtures.models import (
    FIXTURE_BUCKET,
    Field,
    LookupTable,
    LookupTableRow,
    LookupTableRowOwner,
    OwnerType,
    TypeField,
)
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.tests.utils import sharded

DOMAIN = 'fixture-test'
SA_PROVINCES = 'sa_provinces'
FR_PROVINCES = 'fr_provinces'
CA_PROVINCES = 'ca_provinces'


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
        cls.group2 = Group(domain=DOMAIN, name='group2', case_sharing=True, users=[])
        cls.group2.save()

        make_item_lists(SA_PROVINCES, 'western cape'),
        make_item_lists(FR_PROVINCES, 'burgundy', cls.group1),
        make_item_lists(CA_PROVINCES, 'alberta', cls.group2),

        cls.addClassCleanup(get_blob_db().delete, key=FIXTURE_BUCKET + "/" + DOMAIN)

        cls.restore_user = cls.user.to_ota_restore_user(DOMAIN)

    def test_skip_fixture(self):
        device = MockDevice(self.domain, self.restore_user)
        restore = device.sync().payload.decode('utf-8')
        self.assertIn('<fixture ', restore)
        restore_without_fixture = device.sync(skip_fixtures=True).payload.decode('utf-8')
        self.assertNotIn('<fixture ', restore_without_fixture)

    def test_fixture_ownership(self):
        device = MockDevice(self.domain, self.restore_user)
        restore = device.sync().payload.decode('utf-8')
        self.assertIn('<sa_provinces><name>western cape', restore)  # global fixture
        self.assertIn('<fr_provinces><name>burgundy', restore)  # user fixture (owned)
        self.assertNotIn('alberta', restore)  # user fixture (not owned)


def make_item_lists(tag, item_name, group=None):
    data_type = LookupTable(
        domain=DOMAIN,
        tag=tag,
        fields=[TypeField(name="name")],
        item_attributes=[],
        is_global=group is None,
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

    if group is not None:
        LookupTableRowOwner(
            domain=DOMAIN,
            row_id=data_item.id,
            owner_type=OwnerType.Group,
            owner_id=group._id,
        ).save()
    return data_type, data_item
