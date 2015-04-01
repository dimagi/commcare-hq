import uuid
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseRelationship
from casexml.apps.phone.models import OwnershipCleanliness
from casexml.apps.phone.tests.test_sync_mode import SyncBaseTest


class OwnerCleanlinessTest(SyncBaseTest):

    def setUp(self):
        super(OwnerCleanlinessTest, self).setUp()
        self.owner_id = uuid.uuid4().hex
        self.synclog_id = uuid.uuid4().hex
        self.domain = uuid.uuid4().hex
        self.factory = CaseFactory(
            domain=self.domain,
            case_defaults={
                'create': True,
                'owner_id': self.owner_id,
                'user_id': self.owner_id,
            }
        )
        self.assert_owner_clean()  # this first call creates the OwnershipCleanliness doc
        self.sample_case = self.factory.create_case()
        self.child, self.parent = self.factory.create_or_update_case(
            CaseStructure(
                relationships=[
                    CaseRelationship(),
                ]
            )
        )
        self.assert_owner_clean()  # this is an actual assertion

    @property
    def owner_cleanliness(self):
        return OwnershipCleanliness.objects.get_or_create(
            owner_id=self.owner_id,
            domain=self.domain,
            defaults={'is_clean': True}
        )[0]

    def assert_owner_clean(self):
        return self.assertTrue(self.owner_cleanliness.is_clean)

    def assert_owner_dirty(self):
        return self.assertFalse(self.owner_cleanliness.is_clean)

    def _set_owner(self, case_id, owner_id):
        case = self.factory.create_or_update_case(
            CaseStructure(case_id=case_id, attrs={'create': False, 'owner_id': owner_id})
        )[0]
        self.assertEqual(owner_id, case.owner_id)

    def test_add_normal_case_stays_clean(self):
        # change the owner ID of a normal case, should remain clean
        self.factory.create_case()
        self.assert_owner_clean()

    def test_change_owner_stays_clean(self):
        # change the owner ID of a normal case, should remain clean
        new_owner = uuid.uuid4().hex
        self._set_owner(self.sample_case._id, new_owner)
        self.assert_owner_clean()

    def test_change_owner_child_case_stays_clean(self):
        # change the owner ID of a child case, should remain clean
        new_owner = uuid.uuid4().hex
        self._set_owner(self.child._id, new_owner)
        self.assert_owner_clean()

    def test_add_clean_parent_stays_clean(self):
        # add a parent with the same owner, should remain clean
        self.factory.create_or_update_case(CaseStructure(relationships=[CaseRelationship()]))
        self.assert_owner_clean()

    def test_create_dirty_makes_dirty(self):
        # create a case and a parent case with a different owner at the same time
        # make sure the owner becomes dirty.
        new_owner = uuid.uuid4().hex
        self.factory.create_or_update_case(
            CaseStructure(
                relationships=[
                    CaseRelationship(CaseStructure(attrs={'owner_id': new_owner}))
                ]
            )
        )
        self.assert_owner_dirty()

    def test_add_dirty_parent_makes_dirty(self):
        # add parent with a different owner and make sure the owner becomes dirty
        new_owner = uuid.uuid4().hex
        self.factory.create_or_update_case(
            CaseStructure(
                case_id=self.sample_case._id,
                relationships=[
                    CaseRelationship(CaseStructure(attrs={'owner_id': new_owner}))
                ]
            )
        )
        self.assert_owner_dirty()

    def test_change_parent_owner_makes_dirty(self):
        # change the owner id of a parent case and make sure the owner becomes dirty
        new_owner = uuid.uuid4().hex
        self._set_owner(self.parent._id, new_owner)
        self.assert_owner_dirty()
