from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from django.test import SimpleTestCase, TestCase
from django.test.utils import override_settings
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from casexml.apps.case.const import CASE_INDEX_EXTENSION, UNOWNED_EXTENSION_OWNER_ID
from casexml.apps.case.tests.util import delete_all_cases
from casexml.apps.phone.cleanliness import set_cleanliness_flags, hint_still_valid, \
    get_cleanliness_flag_from_scratch, get_case_footprint_info, get_dependent_case_info
from casexml.apps.phone.data_providers.case.clean_owners import pop_ids
from casexml.apps.phone.exceptions import InvalidDomainError, InvalidOwnerIdError
from casexml.apps.phone.models import OwnershipCleanlinessFlag
from casexml.apps.phone.tests.test_sync_mode import DeprecatedBaseSyncTest
from corehq.form_processor.tests.utils import use_sql_backend
from six.moves import range


@override_settings(TESTS_SHOULD_TRACK_CLEANLINESS=None)
class OwnerCleanlinessTest(DeprecatedBaseSyncTest):

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
                indices=[
                    CaseIndex(),
                ]
            )
        )
        self.extension, self.host = self.factory.create_or_update_case(
            CaseStructure(
                attrs={'owner_id': UNOWNED_EXTENSION_OWNER_ID},
                indices=[
                    CaseIndex(
                        relationship=CASE_INDEX_EXTENSION
                    ),
                ]
            )
        )
        self.assert_owner_clean()  # this is an actual assertion

    def _verify_set_cleanliness_flags(self, owner_id=None):
        """
        Can be run at the end of any relevant test to check the current state of the
        OwnershipCleanliness object and verify that rebuilding it from scratch produces
        the same result
        """
        if owner_id is None:
            owner_id = self.owner_id
        owner_cleanliness = self._owner_cleanliness_for_id(owner_id)
        is_clean = owner_cleanliness.is_clean
        hint = owner_cleanliness.hint
        owner_cleanliness.delete()
        set_cleanliness_flags(self.domain, owner_id, force_full=True)
        new_cleanliness = OwnershipCleanlinessFlag.objects.get(owner_id=owner_id)
        self.assertEqual(is_clean, new_cleanliness.is_clean)
        self.assertEqual(hint, new_cleanliness.hint)
        if hint:
            self.assertTrue(hint_still_valid(self.domain, hint))

    @property
    def owner_cleanliness(self):
        return self._owner_cleanliness_for_id(self.owner_id)

    def _owner_cleanliness_for_id(self, owner_id):
        return OwnershipCleanlinessFlag.objects.get_or_create(
            owner_id=owner_id,
            domain=self.domain,
            defaults={'is_clean': True}
        )[0]

    def assert_owner_clean(self):
        self.assertTrue(self.owner_cleanliness.is_clean)

    def assert_owner_dirty(self):
        self.assertFalse(self.owner_cleanliness.is_clean)

    def assert_owner_temporarily_dirty(self):
        """
        Changing any case's owner makes the previous owner ID temporarily dirty, to allow
        syncs to happen, but the should become clean on a rebuild.

        This checks that workflow and rebuilds the cleanliness flag.
        """
        self.assertFalse(self.owner_cleanliness.is_clean)
        set_cleanliness_flags(self.domain, self.owner_id, force_full=True)
        self.assertTrue(self.owner_cleanliness.is_clean)

    def _set_owner(self, case_id, owner_id):
        case = self.factory.create_or_update_case(
            CaseStructure(case_id=case_id, attrs={'create': False, 'owner_id': owner_id})
        )[0]
        self.assertEqual(owner_id, case.owner_id)

    def test_add_normal_case_stays_clean(self):
        """Owned case with no indices remains clean"""
        self.factory.create_case()
        self.assert_owner_clean()
        self._verify_set_cleanliness_flags()

    def test_change_owner_stays_clean(self):
        """change the owner ID of a normal case, should remain clean"""
        new_owner = uuid.uuid4().hex
        self._set_owner(self.sample_case.case_id, new_owner)
        self.assert_owner_temporarily_dirty()
        self._verify_set_cleanliness_flags()

    def test_change_owner_child_case_stays_clean(self):
        """change the owner ID of a child case, should remain clean"""
        new_owner = uuid.uuid4().hex
        self._set_owner(self.child.case_id, new_owner)
        self.assert_owner_temporarily_dirty()
        self._verify_set_cleanliness_flags()

    def test_add_clean_parent_stays_clean(self):
        """add a parent with the same owner, should remain clean"""
        self.factory.create_or_update_case(CaseStructure(indices=[CaseIndex()]))
        self.assert_owner_clean()
        self._verify_set_cleanliness_flags()

    def test_create_dirty_makes_dirty(self):
        """create a case and a parent case with a different owner at the same time
        make sure the owner becomes dirty.
        """
        new_owner = uuid.uuid4().hex
        [child, parent] = self.factory.create_or_update_case(
            CaseStructure(
                indices=[
                    CaseIndex(CaseStructure(attrs={'owner_id': new_owner}))
                ]
            )
        )
        self.assert_owner_dirty()
        self.assertEqual(child.case_id, self.owner_cleanliness.hint)
        self._verify_set_cleanliness_flags()

    def test_add_dirty_parent_makes_dirty(self):
        """add parent with a different owner and make sure the owner becomes dirty"""
        new_owner = uuid.uuid4().hex
        [child, parent] = self.factory.create_or_update_case(
            CaseStructure(
                case_id=self.sample_case.case_id,
                indices=[
                    CaseIndex(CaseStructure(attrs={'owner_id': new_owner}))
                ]
            )
        )
        self.assert_owner_dirty()
        self.assertEqual(child.case_id, self.owner_cleanliness.hint)
        self._verify_set_cleanliness_flags()

    def test_change_parent_owner_makes_dirty(self):
        """change the owner id of a parent case and make sure the owner becomes dirty"""
        new_owner = uuid.uuid4().hex
        self._set_owner(self.parent.case_id, new_owner)
        self.assert_owner_dirty()
        self.assertEqual(self.child.case_id, self.owner_cleanliness.hint)
        self._verify_set_cleanliness_flags()

    def test_change_host_owner_remains_clean(self):
        """change owner for unowned extension, owner remains clean"""
        new_owner = uuid.uuid4().hex
        self._owner_cleanliness_for_id(new_owner)
        self._set_owner(self.host.case_id, new_owner)

        self.assert_owner_temporarily_dirty()
        self.assertTrue(self._owner_cleanliness_for_id(new_owner).is_clean)
        self._verify_set_cleanliness_flags()

    def test_change_host_owner_makes_both_owners_dirty(self):
        """change owner for extension, both owners dirty"""
        new_owner = uuid.uuid4().hex
        self._owner_cleanliness_for_id(new_owner)
        self._set_owner(self.extension.case_id, new_owner)
        self.assert_owner_dirty()
        self.assertFalse(self._owner_cleanliness_for_id(new_owner).is_clean)

    def test_set_flag_clean_no_data(self):
        unused_owner_id = uuid.uuid4().hex
        set_cleanliness_flags(self.domain, unused_owner_id)
        self.assertTrue(OwnershipCleanlinessFlag.objects.get(owner_id=unused_owner_id).is_clean)

    def test_hint_invalidation(self):
        new_owner = uuid.uuid4().hex
        self._set_owner(self.parent.case_id, new_owner)
        self._set_owner(self.parent.case_id, self.owner_id)
        # after the submission the dirtiness flag should still be set
        # since it isn't invalidated right away
        self.assert_owner_dirty()
        # explicitly make sure the hint is no longer valid
        self.assertFalse(hint_still_valid(self.domain, self.owner_cleanliness.hint))
        # reset the cleanliness flag and ensure it worked
        set_cleanliness_flags(self.domain, self.owner_id)
        self.assert_owner_clean()
        self.assertEqual(None, self.owner_cleanliness.hint)

    def test_hint_invalidation_extensions(self):
        other_owner_id = uuid.uuid4().hex
        [extension, host] = self.factory.create_or_update_case(
            CaseStructure(
                case_id='extension',
                attrs={'owner_id': other_owner_id},
                indices=[
                    CaseIndex(
                        CaseStructure(case_id="host"),
                        relationship=CASE_INDEX_EXTENSION
                    )
                ]
            )
        )
        self.assert_owner_dirty()
        self.assertTrue(hint_still_valid(self.domain, self.owner_cleanliness.hint))

        self._set_owner(extension.case_id, UNOWNED_EXTENSION_OWNER_ID)
        self.assertFalse(hint_still_valid(self.domain, self.owner_cleanliness.hint))

    def test_hint_invalidation_extension_chain(self):
        other_owner_id = uuid.uuid4().hex
        self._owner_cleanliness_for_id(other_owner_id)
        host = CaseStructure(case_id=self.sample_case.case_id, attrs={'create': False})
        extension_1 = CaseStructure(
            case_id="extension1",
            attrs={'owner_id': UNOWNED_EXTENSION_OWNER_ID},
            indices=[
                CaseIndex(
                    host,
                    relationship=CASE_INDEX_EXTENSION,
                )
            ]
        )
        extension_2 = CaseStructure(
            case_id="extension2",
            attrs={'owner_id': other_owner_id},
            indices=[
                CaseIndex(
                    extension_1,
                    relationship=CASE_INDEX_EXTENSION,
                )
            ]
        )
        self.factory.create_or_update_case(extension_2)
        self.assert_owner_dirty()

        self._set_owner(extension_2.case_id, UNOWNED_EXTENSION_OWNER_ID)
        self.assertFalse(hint_still_valid(self.domain, self.owner_cleanliness.hint))

    def test_cross_domain_on_submission(self):
        """create a form that makes a dirty owner with the same ID but in a different domain
        make sure the original owner stays clean"""
        new_domain = uuid.uuid4().hex
        # initialize the new cleanliness flag
        OwnershipCleanlinessFlag.objects.create(domain=new_domain, owner_id=self.owner_id, is_clean=True)
        self.factory.domain = new_domain
        self.factory.create_or_update_case(
            CaseStructure(
                indices=[
                    CaseIndex(CaseStructure(attrs={'owner_id': uuid.uuid4().hex}))
                ]
            )
        )
        self.assert_owner_clean()
        self.assertEqual(
            False,
            OwnershipCleanlinessFlag.objects.get(owner_id=self.owner_id, domain=new_domain).is_clean,
        )

    def test_cross_domain_both_clean(self):
        new_domain = uuid.uuid4().hex
        self.factory.domain = new_domain
        self.factory.create_or_update_case(
            CaseStructure(
                indices=[
                    CaseIndex(),
                ]
            )
        )
        # two clean ownership models in different domains should report clean
        self.assertTrue(get_cleanliness_flag_from_scratch(self.domain, self.owner_id).is_clean)
        self.assertTrue(get_cleanliness_flag_from_scratch(new_domain, self.owner_id).is_clean)

    def test_cross_domain_dirty(self):
        new_domain = uuid.uuid4().hex
        new_owner = uuid.uuid4().hex
        self.factory.domain = new_domain
        self.factory.create_or_update_case(
            CaseStructure(
                indices=[
                    CaseIndex(CaseStructure(attrs={'owner_id': new_owner})),
                ]
            )
        )
        # original domain should stay clean but the new one should be dirty
        self.assertTrue(get_cleanliness_flag_from_scratch(self.domain, self.owner_id).is_clean)
        self.assertFalse(get_cleanliness_flag_from_scratch(new_domain, self.owner_id).is_clean)

    def test_non_existent_parent(self):
        self.factory.create_or_update_case(
            CaseStructure(
                indices=[
                    CaseIndex(CaseStructure()),
                ],
                walk_related=False,
            )
        )
        self.assertTrue(get_cleanliness_flag_from_scratch(self.domain, self.owner_id).is_clean)

    @override_settings(TESTS_SHOULD_TRACK_CLEANLINESS=False)
    def test_autocreate_flag_off(self):
        new_owner = uuid.uuid4().hex
        self.factory.create_or_update_case(
            CaseStructure(case_id=uuid.uuid4().hex, attrs={'create': True, 'owner_id': new_owner})
        )[0]
        self.assertFalse(OwnershipCleanlinessFlag.objects.filter(domain=self.domain, owner_id=new_owner).exists())

    @override_settings(TESTS_SHOULD_TRACK_CLEANLINESS=True)
    def test_autocreate_flag_on(self):
        new_owner = uuid.uuid4().hex
        self.factory.create_or_update_case(
            CaseStructure(case_id=uuid.uuid4().hex, attrs={'create': True, 'owner_id': new_owner})
        )[0]
        flag = OwnershipCleanlinessFlag.objects.get(domain=self.domain, owner_id=new_owner)
        self.assertEqual(True, flag.is_clean)

    def test_simple_unowned_extension(self):
        """Simple unowned extensions should be clean"""
        self.factory.create_or_update_case(
            CaseStructure(
                case_id=uuid.uuid4().hex,
                attrs={'owner_id': UNOWNED_EXTENSION_OWNER_ID},
                indices=[
                    CaseIndex(
                        CaseStructure(),
                        relationship=CASE_INDEX_EXTENSION
                    )
                ]
            )
        )
        self.assert_owner_clean()
        self._verify_set_cleanliness_flags()

    def test_owned_extension(self):
        """Extension owned by another owner should be dirty"""
        other_owner_id = uuid.uuid4().hex
        self._owner_cleanliness_for_id(other_owner_id)
        [extension, host] = self.factory.create_or_update_case(
            CaseStructure(
                case_id='extension',
                attrs={'owner_id': other_owner_id},
                indices=[
                    CaseIndex(
                        CaseStructure(case_id="host"),
                        relationship=CASE_INDEX_EXTENSION
                    )
                ]
            )
        )
        self.assert_owner_dirty()
        self.assertFalse(self._owner_cleanliness_for_id(other_owner_id).is_clean)
        self.assertEqual(host.case_id, self.owner_cleanliness.hint)
        self.assertEqual(extension.case_id, self._owner_cleanliness_for_id(other_owner_id).hint)
        self._verify_set_cleanliness_flags(self.owner_id)
        self._verify_set_cleanliness_flags(other_owner_id)

    def test_extension_chain_with_other_owner_makes_dirty(self):
        """An extension chain of unowned extensions that ends at a case owned by a different owner is dirty"""
        other_owner_id = uuid.uuid4().hex
        self._owner_cleanliness_for_id(other_owner_id)
        host = CaseStructure(case_id=self.sample_case.case_id, attrs={'create': False})
        extension_1 = CaseStructure(
            case_id="extension1",
            attrs={'owner_id': UNOWNED_EXTENSION_OWNER_ID},
            indices=[
                CaseIndex(
                    host,
                    relationship=CASE_INDEX_EXTENSION,
                )
            ]
        )
        extension_2 = CaseStructure(
            case_id="extension2",
            attrs={'owner_id': other_owner_id},
            indices=[
                CaseIndex(
                    extension_1,
                    relationship=CASE_INDEX_EXTENSION,
                )
            ]
        )
        self.factory.create_or_update_case(extension_2)

        self.assert_owner_dirty()
        self.assertFalse(self._owner_cleanliness_for_id(other_owner_id).is_clean)
        self.assertEqual(host.case_id, self.owner_cleanliness.hint)
        self.assertEqual(extension_2.case_id, self._owner_cleanliness_for_id(other_owner_id).hint)
        self._verify_set_cleanliness_flags(self.owner_id)
        self._verify_set_cleanliness_flags(other_owner_id)

    def test_multiple_indices_multiple_owners(self):
        """Extension that indexes a case with another owner should make all owners dirty"""
        other_owner_id = uuid.uuid4().hex
        self._owner_cleanliness_for_id(other_owner_id)
        host_1 = CaseStructure()
        host_2 = CaseStructure(attrs={'owner_id': other_owner_id})

        self.factory.create_or_update_case(
            CaseStructure(
                case_id=self.sample_case.case_id,
                attrs={'owner_id': UNOWNED_EXTENSION_OWNER_ID},
                indices=[
                    CaseIndex(
                        host_1,
                        relationship=CASE_INDEX_EXTENSION,
                        identifier="host_1",
                    ),
                    CaseIndex(
                        host_2,
                        relationship=CASE_INDEX_EXTENSION,
                        identifier="host_2",
                    )
                ]
            )
        )
        self.assert_owner_dirty()
        self.assertFalse(self._owner_cleanliness_for_id(other_owner_id).is_clean)
        self.assertEqual(host_1.case_id, self.owner_cleanliness.hint)
        self.assertEqual(host_2.case_id, self._owner_cleanliness_for_id(other_owner_id).hint)
        self._verify_set_cleanliness_flags(self.owner_id)
        self._verify_set_cleanliness_flags(other_owner_id)

    def test_long_extension_chain_with_branches(self):
        """An extension chain of unowned extensions that ends at an owned case is dirty"""
        owner_1 = uuid.uuid4().hex
        self._owner_cleanliness_for_id(owner_1)
        owner_2 = uuid.uuid4().hex
        self._owner_cleanliness_for_id(owner_2)
        host = CaseStructure(case_id=self.sample_case.case_id, attrs={'create': False})
        host_2 = CaseStructure(
            case_id="host_with_other_owner",
            attrs={'owner_id': owner_1}
        )
        extension_1 = CaseStructure(
            case_id="extension1",
            attrs={'owner_id': UNOWNED_EXTENSION_OWNER_ID},
            indices=[
                CaseIndex(
                    host,
                    relationship=CASE_INDEX_EXTENSION,
                    identifier="host_1",
                ),
                CaseIndex(
                    host_2,
                    relationship=CASE_INDEX_EXTENSION,
                    identifier="host_2",
                )
            ]
        )
        extension_2 = CaseStructure(
            case_id="extension2",
            attrs={'owner_id': owner_2},
            indices=[
                CaseIndex(
                    extension_1,
                    relationship=CASE_INDEX_EXTENSION,
                )
            ]
        )
        self.factory.create_or_update_case(extension_2)
        self.assert_owner_dirty()
        self.assertFalse(self._owner_cleanliness_for_id(owner_1).is_clean)
        self.assertFalse(self._owner_cleanliness_for_id(owner_2).is_clean)
        self.assertEqual(host.case_id, self.owner_cleanliness.hint)
        self._verify_set_cleanliness_flags()

    def test_extension_of_parent(self):
        # child case owned by owner
        # parent case not owned
        # parent has extension also not owned
        other_owner = uuid.uuid4().hex
        parent = CaseStructure(
            case_id='parent_owned_by_other_owner',
            attrs={'create': True, 'owner_id': other_owner}
        )

        child = CaseStructure(
            case_id='child_owned_by_owner',
            attrs={'create': True, 'owner_id': self.owner_id},
            indices=[
                CaseIndex(
                    parent,
                    identifier="retainer",
                ),
            ]
        )
        extension = CaseStructure(
            case_id="extension_owned_by_other_owner",
            attrs={'owner_id': other_owner},
            indices=[
                CaseIndex(
                    parent,
                    relationship=CASE_INDEX_EXTENSION,
                    identifier="host_1",
                ),
            ]
        )
        self.factory.create_or_update_case(extension)
        self.factory.create_or_update_case(child)
        self.assert_owner_dirty()
        self.assertTrue(self._owner_cleanliness_for_id(other_owner).is_clean)
        self.assertEqual(child.case_id, self.owner_cleanliness.hint)
        self._verify_set_cleanliness_flags()


@use_sql_backend
class OwnerCleanlinessTestSQL(OwnerCleanlinessTest):
    pass


class SetCleanlinessFlagsTest(TestCase):

    def test_set_bad_domains(self):
        test_cases = [None, '', 'something-too-long' * 10]
        for invalid_domain in test_cases:
            with self.assertRaises(InvalidDomainError):
                set_cleanliness_flags(invalid_domain, 'whatever')

    def test_set_bad_owner_ids(self):
        test_cases = [None, '', 'something-too-long' * 10]
        for invalid_owner in test_cases:
            with self.assertRaises(InvalidOwnerIdError):
                set_cleanliness_flags('whatever', invalid_owner)


@use_sql_backend
class SetCleanlinessFlagsTestSQL(SetCleanlinessFlagsTest):
    pass


class CleanlinessUtilitiesTest(SimpleTestCase):

    def test_pop_ids(self):
        five = set(range(5))
        three = pop_ids(five, 3)
        self.assertEqual(3, len(three))
        self.assertEqual(2, len(five))
        self.assertEqual(five | set(three), set(range(5)))

    def test_pop_ids_too_many(self):
        five = set(range(5))
        back = pop_ids(five, 6)
        self.assertEqual(5, len(back))
        self.assertEqual(0, len(five))
        self.assertEqual(set(back), set(range(5)))


class GetCaseFootprintInfoTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(GetCaseFootprintInfoTest, cls).setUpClass()
        delete_all_cases()

    def setUp(self):
        super(GetCaseFootprintInfoTest, self).setUp()
        self.domain = 'domain'
        self.owner_id = uuid.uuid4().hex
        self.other_owner_id = uuid.uuid4().hex
        self.factory = CaseFactory(self.domain)

    def test_simple_footprint(self):
        """ should only return open cases from user """
        case = CaseStructure(case_id=uuid.uuid4().hex, attrs={'owner_id': self.owner_id, 'create': True})
        closed_case = CaseStructure(case_id=uuid.uuid4().hex, attrs={'owner_id': self.owner_id, 'close': True, 'create': True})
        other_case = CaseStructure(case_id=uuid.uuid4().hex, attrs={'owner_id': self.other_owner_id, 'create': True})
        self.factory.create_or_update_cases([case, other_case, closed_case])

        footprint_info = get_case_footprint_info(self.domain, self.owner_id)
        self.assertEqual(footprint_info.all_ids, set([case.case_id]))

    def test_footprint_with_parent(self):
        """ should return open cases with parents """
        parent = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.other_owner_id, 'close': True, 'create': True}
        )
        child = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.owner_id, 'create': True},
            indices=[CaseIndex(parent)]
        )

        self.factory.create_or_update_cases([parent, child])

        footprint_info = get_case_footprint_info(self.domain, self.owner_id)
        self.assertEqual(footprint_info.all_ids, set([child.case_id, parent.case_id]))
        self.assertEqual(footprint_info.base_ids, set([child.case_id]))

    def test_footprint_with_extension(self):
        """
        Extensions are brought in if the host case is owned;
        Host case is brought in if the extension is owned
        """
        host = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.owner_id, 'create': True}
        )
        extension = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.other_owner_id, 'create': True},
            indices=[CaseIndex(host, relationship=CASE_INDEX_EXTENSION)]
        )

        self.factory.create_or_update_cases([host, extension])
        footprint_info = get_case_footprint_info(self.domain, self.owner_id)
        self.assertEqual(footprint_info.all_ids, set([extension.case_id, host.case_id]))
        self.assertEqual(footprint_info.base_ids, set([host.case_id]))

        footprint_info = get_case_footprint_info(self.domain, self.other_owner_id)
        self.assertEqual(footprint_info.all_ids, set([extension.case_id, host.case_id]))
        self.assertEqual(footprint_info.base_ids, set([extension.case_id]))

    def test_footprint_with_extension_of_parent(self):
        """ Extensions of parents should be included """
        parent = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.other_owner_id, 'close': True, 'create': True}
        )
        child = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.owner_id, 'create': True},
            indices=[CaseIndex(parent)]
        )
        extension = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.other_owner_id, 'create': True},
            indices=[CaseIndex(parent, relationship=CASE_INDEX_EXTENSION)]
        )
        self.factory.create_or_update_cases([parent, child, extension])
        footprint_info = get_case_footprint_info(self.domain, self.owner_id)
        self.assertEqual(footprint_info.all_ids, set([extension.case_id, parent.case_id, child.case_id]))

    def test_footprint_with_extension_of_child(self):
        """ Extensions of children should be included """
        parent = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.other_owner_id, 'create': True, 'close': True}
        )
        child = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.owner_id, 'create': True},
            indices=[CaseIndex(parent)]
        )
        extension = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.other_owner_id, 'create': True},
            indices=[CaseIndex(child, relationship=CASE_INDEX_EXTENSION)]
        )
        self.factory.create_or_update_cases([parent, child, extension])
        footprint_info = get_case_footprint_info(self.domain, self.owner_id)
        self.assertEqual(footprint_info.all_ids, set([extension.case_id, parent.case_id, child.case_id]))

    def test_cousins(self):
        # http://manage.dimagi.com/default.asp?189528
        grandparent = CaseStructure(
            case_id="Steffon",
            attrs={'owner_id': self.other_owner_id, 'create': True}
        )
        parent_1 = CaseStructure(
            case_id="Stannis",
            attrs={'owner_id': self.other_owner_id, 'create': True},
            indices=[CaseIndex(grandparent)]
        )
        parent_2 = CaseStructure(
            case_id="Robert",
            attrs={'owner_id': self.other_owner_id, 'create': True},
            indices=[CaseIndex(grandparent)]
        )
        child_1 = CaseStructure(
            case_id="Shireen",
            attrs={'owner_id': self.owner_id, 'create': True},
            indices=[CaseIndex(parent_1)]
        )
        child_2 = CaseStructure(
            case_id="Joffrey",
            attrs={'owner_id': self.owner_id, 'create': True},
            indices=[CaseIndex(parent_2)]
        )
        self.factory.create_or_update_cases([grandparent, parent_1, parent_2, child_1, child_2])
        footprint_info = get_case_footprint_info(self.domain, self.owner_id)
        self.assertEqual(
            footprint_info.all_ids,
            set([grandparent.case_id,
                 parent_1.case_id,
                 parent_2.case_id,
                 child_1.case_id,
                 child_2.case_id])
        )


@use_sql_backend
class GetCaseFootprintInfoTestSQL(GetCaseFootprintInfoTest):
    pass


class GetDependentCasesTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(GetDependentCasesTest, cls).setUpClass()
        delete_all_cases()

    def setUp(self):
        super(GetDependentCasesTest, self).setUp()
        self.domain = 'domain'
        self.owner_id = uuid.uuid4().hex
        self.other_owner_id = uuid.uuid4().hex
        self.factory = CaseFactory(self.domain)

    def test_returns_nothing_with_no_dependencies(self):
        case = self.factory.create_case()
        self.assertEqual(set(), get_dependent_case_info(self.domain, [case.case_id]).all_ids)

    def test_returns_simple_extension(self):
        host = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.owner_id, 'create': True}
        )
        extension = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.other_owner_id, 'create': True},
            indices=[CaseIndex(host, relationship=CASE_INDEX_EXTENSION)]
        )
        all_ids = set([host.case_id, extension.case_id])

        self.factory.create_or_update_cases([host, extension])
        self.assertEqual(all_ids, get_dependent_case_info(self.domain, [host.case_id]).all_ids)
        self.assertEqual(all_ids, get_dependent_case_info(self.domain, [extension.case_id]).all_ids)
        self.assertEqual(set([extension.case_id]),
                         get_dependent_case_info(self.domain, [host.case_id]).extension_ids)

    def test_returns_extension_of_extension(self):
        host = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.owner_id, 'create': True}
        )
        extension = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.other_owner_id, 'create': True},
            indices=[CaseIndex(host, relationship=CASE_INDEX_EXTENSION)]
        )
        extension_2 = CaseStructure(
            case_id=uuid.uuid4().hex,
            indices=[CaseIndex(extension, relationship=CASE_INDEX_EXTENSION)],
            attrs={'create': True}
        )
        all_ids = set([host.case_id, extension.case_id, extension_2.case_id])

        self.factory.create_or_update_cases([extension_2])
        self.assertEqual(all_ids, get_dependent_case_info(self.domain, [host.case_id]).all_ids)
        self.assertEqual(all_ids, get_dependent_case_info(self.domain, [extension.case_id]).all_ids)
        self.assertEqual(all_ids, get_dependent_case_info(self.domain, [extension_2.case_id]).all_ids)
        self.assertEqual(set([extension.case_id, extension_2.case_id]),
                         get_dependent_case_info(self.domain, [host.case_id]).extension_ids)

    def test_children_and_extensions(self):
        parent = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.other_owner_id, 'close': True, 'create': True}
        )
        child = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.owner_id, 'create': True},
            indices=[CaseIndex(parent)]
        )
        extension = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'owner_id': self.other_owner_id, 'create': True},
            indices=[CaseIndex(child, relationship=CASE_INDEX_EXTENSION)]
        )
        self.factory.create_or_update_cases([parent, child, extension])
        all_ids = set([parent.case_id, child.case_id, extension.case_id])
        self.assertEqual(all_ids, get_dependent_case_info(self.domain, [child.case_id]).all_ids)
        self.assertEqual(set([]), get_dependent_case_info(self.domain, [parent.case_id]).all_ids)
        self.assertEqual(set([extension.case_id]),
                         get_dependent_case_info(self.domain, [child.case_id]).extension_ids)
        self.assertEqual(set([]),
                         get_dependent_case_info(self.domain, [parent.case_id]).extension_ids)


@use_sql_backend
class GetDependentCasesTestSQL(GetDependentCasesTest):
    pass
