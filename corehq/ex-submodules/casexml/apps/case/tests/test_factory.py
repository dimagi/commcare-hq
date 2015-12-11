import uuid

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from casexml.apps.case.const import DEFAULT_CASE_INDEX_IDENTIFIERS
from casexml.apps.case.mock import CaseStructure, CaseIndex, CaseFactory
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.toggles import LOOSE_SYNC_TOKEN_VALIDATION


class CaseRelationshipTest(SimpleTestCase):

    def test_defaults(self):
        relationship = CaseIndex()
        self.assertIsNotNone(relationship.related_structure.case_id)
        self.assertEqual(relationship.DEFAULT_RELATIONSHIP, relationship.relationship)
        self.assertEqual(relationship.DEFAULT_RELATED_CASE_TYPE, relationship.related_type)

    def test_default_type_from_relationship(self):
        relationship = CaseIndex(CaseStructure(attrs={'case_type': 'custom_type'}))
        self.assertEqual('custom_type', relationship.related_type)


class CaseStructureTest(SimpleTestCase):

    def test_index(self):
        parent_case_id = uuid.uuid4().hex
        structure = CaseStructure(
            indices=[
                CaseIndex(CaseStructure(case_id=parent_case_id))
            ]
        )
        self.assertEqual(
            {DEFAULT_CASE_INDEX_IDENTIFIERS[CaseIndex.DEFAULT_RELATIONSHIP]:
             (CaseIndex.DEFAULT_RELATED_CASE_TYPE, parent_case_id,
              CaseIndex.DEFAULT_RELATIONSHIP)},
            structure.index,
        )

    def test_multiple_indices(self):
        indices = [
            ('mother_case_id', 'parent', 'mother_type', 'mother'),
            ('father_case_id', 'parent', 'father_type', 'father'),
        ]
        structure = CaseStructure(
            indices=[
                CaseIndex(CaseStructure(case_id=i[0]), relationship=i[1], related_type=i[2],
                          identifier=i[3])
                for i in indices
            ]
        )
        self.assertEqual(
            {i[3]: (i[2], i[0], i[1]) for i in indices},
            structure.index,
        )

    def test_walk_ids(self):
        case_id = uuid.uuid4().hex
        parent_case_id = uuid.uuid4().hex
        grandparent_case_id = uuid.uuid4().hex
        structure = CaseStructure(
            case_id=case_id,
            indices=[
                CaseIndex(CaseStructure(
                    case_id=parent_case_id,
                    indices=[
                        CaseIndex(CaseStructure(case_id=grandparent_case_id))
                    ]))
            ]
        )
        self.assertEqual(
            [case_id, parent_case_id, grandparent_case_id],
            list(structure.walk_ids())
        )

    def test_walk_ids_ignore_related(self):
        case_id = uuid.uuid4().hex
        parent_case_id = uuid.uuid4().hex
        grandparent_case_id = uuid.uuid4().hex
        structure = CaseStructure(
            case_id=case_id,
            indices=[
                CaseIndex(CaseStructure(
                    case_id=parent_case_id,
                    indices=[
                        CaseIndex(CaseStructure(case_id=grandparent_case_id))
                    ]))
            ]
        )
        structure.walk_related = False
        self.assertEqual(
            [case_id],
            list(structure.walk_ids())
        )
        structure.walk_related = True
        structure.indices[0].related_structure.walk_related = False
        self.assertEqual(
            [case_id, parent_case_id],
            list(structure.walk_ids())
        )


class CaseFactoryTest(TestCase):

    @run_with_all_backends
    def test_simple_create(self):
        factory = CaseFactory()
        case = factory.create_case()
        self.assertIsNotNone(CaseAccessors().get_case(case.case_id))

    @run_with_all_backends
    def test_create_overrides(self):
        factory = CaseFactory()
        case = factory.create_case(owner_id='somebody', update={'custom_prop': 'custom_value'})
        self.assertEqual('somebody', case.owner_id)
        self.assertEqual('custom_value', case.dynamic_case_properties()['custom_prop'])

    @run_with_all_backends
    def test_domain(self):
        domain = uuid.uuid4().hex
        factory = CaseFactory(domain=domain)
        case = factory.create_case()
        self.assertEqual(domain, case.domain)

    @run_with_all_backends
    def test_factory_defaults(self):
        owner_id = uuid.uuid4().hex
        factory = CaseFactory(case_defaults={'owner_id': owner_id})
        case = factory.create_case()
        self.assertEqual(owner_id, case.owner_id)

    @run_with_all_backends
    def test_override_defaults(self):
        owner_id = uuid.uuid4().hex
        factory = CaseFactory(case_defaults={'owner_id': owner_id})
        case = factory.create_case(owner_id='notthedefault')
        self.assertEqual('notthedefault', case.owner_id)

    @run_with_all_backends
    def test_create_from_structure(self):
        owner_id = uuid.uuid4().hex
        factory = CaseFactory(case_defaults={
            'owner_id': owner_id,
            'create': True,
            'update': {'custom_prop': 'custom_value'}
        })
        case_id = uuid.uuid4().hex
        child_case_id = uuid.uuid4().hex
        parent_case_id = uuid.uuid4().hex
        structures = [
            CaseStructure(case_id=case_id),
            CaseStructure(
                case_id=child_case_id,
                indices=[
                    CaseIndex(CaseStructure(case_id=parent_case_id))
                ]
            )
        ]
        cases = factory.create_or_update_cases(structures)
        for case in cases:
            self.assertEqual(owner_id, case.owner_id)
            self.assertEqual('custom_value', case.dynamic_case_properties()['custom_prop'])

        [regular, child, parent] = cases
        self.assertEqual(1, len(child.indices))
        self.assertEqual(parent_case_id, child.indices[0].referenced_id)
        if not settings.TESTS_SHOULD_USE_SQL_BACKEND:
            self.assertEqual(2, len(regular.actions))  # create + update
            self.assertEqual(2, len(parent.actions))  # create + update
            self.assertEqual(3, len(child.actions))  # create + update + index

    @run_with_all_backends
    def test_no_walk_related(self):
        factory = CaseFactory()
        parent = factory.create_case()
        child_updates = factory.create_or_update_case(
            CaseStructure(attrs={'create': True}, walk_related=False, indices=[
                CaseIndex(CaseStructure(case_id=parent.case_id))
            ]),
        )
        self.assertEqual(1, len(child_updates))
        self.assertEqual(parent.case_id, child_updates[0].indices[0].referenced_id)

    @run_with_all_backends
    def test_form_extras(self):
        domain = uuid.uuid4().hex
        LOOSE_SYNC_TOKEN_VALIDATION.set(domain, True, namespace='domain')
        token_id = uuid.uuid4().hex
        factory = CaseFactory(domain=domain)
        [case] = factory.create_or_update_case(CaseStructure(), form_extras={'last_sync_token': token_id})
        form = FormAccessors(domain).get_form(case.xform_ids[0])
        self.assertEqual(token_id, form.last_sync_token)

    @run_with_all_backends
    def test_form_extras_default(self):
        domain = uuid.uuid4().hex
        # have to enable loose sync token validation for the domain or create actual SyncLog documents.
        # this is the easier path.
        LOOSE_SYNC_TOKEN_VALIDATION.set(domain, True, namespace='domain')
        token_id = uuid.uuid4().hex
        factory = CaseFactory(domain=domain, form_extras={'last_sync_token': token_id})
        case = factory.create_case()
        form = FormAccessors(domain).get_form(case.xform_ids[0])
        self.assertEqual(token_id, form.last_sync_token)

    @run_with_all_backends
    def test_form_extras_override_defaults(self):
        domain = uuid.uuid4().hex
        LOOSE_SYNC_TOKEN_VALIDATION.set(domain, True, namespace='domain')
        token_id = uuid.uuid4().hex
        factory = CaseFactory(domain=domain, form_extras={'last_sync_token': token_id})
        [case] = factory.create_or_update_case(CaseStructure(), form_extras={'last_sync_token': 'differenttoken'})
        form = FormAccessors(domain).get_form(case.xform_ids[0])
        self.assertEqual('differenttoken', form.last_sync_token)
