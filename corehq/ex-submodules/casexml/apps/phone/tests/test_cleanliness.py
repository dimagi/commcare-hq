import uuid
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseRelationship
from casexml.apps.phone.cleanliness import set_cleanliness_flags, hint_still_valid
from casexml.apps.phone.models import OwnershipCleanlinessFlag
from casexml.apps.phone.tests.test_sync_mode import SyncBaseTest
from corehq.toggles import OWNERSHIP_CLEANLINESS


class OwnerCleanlinessTest(SyncBaseTest):

    def setUp(self):
        super(OwnerCleanlinessTest, self).setUp()
        # ensure that randomization is on
        OWNERSHIP_CLEANLINESS.randomness = 1
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

    def _verify_set_cleanliness_flags(self):
        """
        Can be run at the end of any relevant test to check the current state of the
        OwnershipCleanliness object and verify that rebuilding it from scratch produces
        the same result
        """
        is_clean = self.owner_cleanliness.is_clean
        hint = self.owner_cleanliness.hint
        self.owner_cleanliness.delete()
        set_cleanliness_flags(self.domain, self.owner_id)
        new_cleanliness = OwnershipCleanlinessFlag.objects.get(owner_id=self.owner_id)
        self.assertEqual(is_clean, new_cleanliness.is_clean)
        self.assertEqual(hint, new_cleanliness.hint)
        if hint:
            self.assertTrue(hint_still_valid(self.domain, self.owner_id, hint))

    @property
    def owner_cleanliness(self):
        return OwnershipCleanlinessFlag.objects.get_or_create(
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
        self._verify_set_cleanliness_flags()

    def test_change_owner_stays_clean(self):
        # change the owner ID of a normal case, should remain clean
        new_owner = uuid.uuid4().hex
        self._set_owner(self.sample_case._id, new_owner)
        self.assert_owner_clean()
        self._verify_set_cleanliness_flags()

    def test_change_owner_child_case_stays_clean(self):
        # change the owner ID of a child case, should remain clean
        new_owner = uuid.uuid4().hex
        self._set_owner(self.child._id, new_owner)
        self.assert_owner_clean()
        self._verify_set_cleanliness_flags()

    def test_add_clean_parent_stays_clean(self):
        # add a parent with the same owner, should remain clean
        self.factory.create_or_update_case(CaseStructure(relationships=[CaseRelationship()]))
        self.assert_owner_clean()
        self._verify_set_cleanliness_flags()

    def test_create_dirty_makes_dirty(self):
        # create a case and a parent case with a different owner at the same time
        # make sure the owner becomes dirty.
        new_owner = uuid.uuid4().hex
        [child, parent] = self.factory.create_or_update_case(
            CaseStructure(
                relationships=[
                    CaseRelationship(CaseStructure(attrs={'owner_id': new_owner}))
                ]
            )
        )
        self.assert_owner_dirty()
        self.assertEqual(child._id, self.owner_cleanliness.hint)
        self._verify_set_cleanliness_flags()

    def test_add_dirty_parent_makes_dirty(self):
        # add parent with a different owner and make sure the owner becomes dirty
        new_owner = uuid.uuid4().hex
        [child, parent] = self.factory.create_or_update_case(
            CaseStructure(
                case_id=self.sample_case._id,
                relationships=[
                    CaseRelationship(CaseStructure(attrs={'owner_id': new_owner}))
                ]
            )
        )
        self.assert_owner_dirty()
        self.assertEqual(child._id, self.owner_cleanliness.hint)
        self._verify_set_cleanliness_flags()

    def test_change_parent_owner_makes_dirty(self):
        # change the owner id of a parent case and make sure the owner becomes dirty
        new_owner = uuid.uuid4().hex
        self._set_owner(self.parent._id, new_owner)
        self.assert_owner_dirty()
        self.assertEqual(self.child._id, self.owner_cleanliness.hint)
        self._verify_set_cleanliness_flags()

    def test_toggle(self):
        # make sure the flag gets removed
        OWNERSHIP_CLEANLINESS.randomness = 0
        # and any test that normally expects a flag to be set to fail
        with self.assertRaises(AssertionError):
            self.test_create_dirty_makes_dirty()

    def test_set_flag_clean_no_data(self):
        unused_owner_id = uuid.uuid4().hex
        set_cleanliness_flags(self.domain, unused_owner_id)
        self.assertTrue(OwnershipCleanlinessFlag.objects.get(owner_id=unused_owner_id).is_clean)

    def test_hint_invalidation(self):
        self.test_change_parent_owner_makes_dirty()
        self._set_owner(self.parent._id, self.owner_id)
        # after the submission the dirtiness flag should still be set
        # since it isn't invalidated right away
        self.assert_owner_dirty()
        # explicitly make sure the hint is no longer valid
        self.assertFalse(hint_still_valid(self.domain, self.owner_id, self.owner_cleanliness.hint))
        # reset the cleanliness flag and ensure it worked
        set_cleanliness_flags(self.domain, self.owner_id)
        self.assert_owner_clean()
        self.assertEqual(None, self.owner_cleanliness.hint)
