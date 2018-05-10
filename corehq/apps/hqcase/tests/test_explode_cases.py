from __future__ import absolute_import

from __future__ import unicode_literals
import uuid
from datetime import datetime

import six
from django.test import TestCase, override_settings

from casexml.apps.case.mock import CaseBlock, CaseIndex, CaseStructure
from casexml.apps.case.tests.util import delete_all_cases, delete_all_ledgers, delete_all_xforms
from casexml.apps.phone.tests.test_sync_mode import BaseSyncTest
from casexml.apps.stock.mock import Balance, Entry
from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.tasks import explode_cases, topological_sort_cases
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import (CaseAccessors,
                                                          LedgerAccessors)
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.util.test_utils import flag_enabled


class ExplodeCasesDbTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(ExplodeCasesDbTest, cls).setUpClass()
        delete_all_cases()
        cls.domain = Domain(name='foo')
        cls.domain.save()
        cls.user = CommCareUser.create(cls.domain.name, 'somebody', 'password')
        cls.user_id = cls.user._id

    def setUp(self):
        self.accessor = CaseAccessors(self.domain.name)
        delete_all_cases()
        delete_all_xforms()

    def tearDown(self):
        delete_all_cases()
        delete_all_xforms()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.domain.delete()
        super(ExplodeCasesDbTest, cls).tearDownClass()

    @run_with_all_backends
    def test_simple(self):
        caseblock = CaseBlock(
            create=True,
            case_id=uuid.uuid4().hex,
            user_id=self.user_id,
            owner_id=self.user_id,
            case_type='exploder-type',
        ).as_string()
        submit_case_blocks([caseblock], self.domain.name)
        self.assertEqual(1, len(self.accessor.get_case_ids_in_domain()))
        explode_cases(self.domain.name, self.user_id, 10)

        case_ids = self.accessor.get_case_ids_in_domain()
        cases_back = list(self.accessor.iter_cases(case_ids))
        self.assertEqual(10, len(cases_back))
        for case in cases_back:
            self.assertEqual(self.user_id, case.owner_id)

    @run_with_all_backends
    def test_skip_user_case(self):
        caseblock = CaseBlock(
            create=True,
            case_id=uuid.uuid4().hex,
            user_id=self.user_id,
            owner_id=self.user_id,
            case_type='commcare-user',
        ).as_string()
        submit_case_blocks([caseblock], self.domain.name)
        self.assertEqual(1, len(self.accessor.get_case_ids_in_domain()))
        explode_cases(self.domain.name, self.user_id, 10)

        case_ids = self.accessor.get_case_ids_in_domain()
        cases_back = list(self.accessor.iter_cases(case_ids))
        self.assertEqual(1, len(cases_back))
        for case in cases_back:
            self.assertEqual(self.user_id, case.owner_id)

    @run_with_all_backends
    def test_parent_child(self):
        parent_id = uuid.uuid4().hex
        parent_type = 'exploder-parent-type'
        parent_block = CaseBlock(
            create=True,
            case_id=parent_id,
            user_id=self.user_id,
            owner_id=self.user_id,
            case_type=parent_type,
        ).as_string()

        child_id = uuid.uuid4().hex
        child_block = CaseBlock(
            create=True,
            case_id=child_id,
            user_id=self.user_id,
            owner_id=self.user_id,
            case_type='exploder-child-type',
            index={'parent': (parent_type, parent_id)},
        ).as_string()

        submit_case_blocks([parent_block, child_block], self.domain.name)
        self.assertEqual(2, len(self.accessor.get_case_ids_in_domain()))

        explode_cases(self.domain.name, self.user_id, 5)
        case_ids = self.accessor.get_case_ids_in_domain()
        cases_back = list(self.accessor.iter_cases(case_ids))
        self.assertEqual(10, len(cases_back))
        parent_cases = {p.case_id: p for p in [case for case in cases_back if case.type == parent_type]}
        self.assertEqual(5, len(parent_cases))
        child_cases = [case for case in cases_back if case.type == 'exploder-child-type']
        self.assertEqual(5, len(child_cases))
        child_indices = [child.indices[0].referenced_id for child in child_cases]
        # make sure they're different
        self.assertEqual(len(child_cases), len(set(child_indices)))
        for child in child_cases:
            self.assertEqual(1, len(child.indices))
            self.assertTrue(child.indices[0].referenced_id in parent_cases)


class ExplodeExtensionsDBTest(BaseSyncTest):

    def setUp(self):
        super(ExplodeExtensionsDBTest, self).setUp()
        self.accessor = CaseAccessors(self.project.name)
        self._create_case_structure()

    def tearDown(self):
        delete_all_cases()
        delete_all_xforms()
        super(ExplodeExtensionsDBTest, self).tearDown()

    def _create_case_structure(self):
        """
                  +----+
                  | H  |
                  +--^-+
                     |e
        +---+     +--+-+
        |C  +--c->| PH |
        +---+     +--^-+
       (owned)       |e
                  +--+-+
                  | E  |
                  +----+
        """
        case_type = 'case'

        H = CaseStructure(
            case_id='host',
            attrs={'create': True, 'owner_id': '-'},
        )  # No outgoing indices, so this is the root

        PH = CaseStructure(
            case_id='parent_host',
            attrs={'create': True, 'owner_id': '-'},
            indices=[CaseIndex(
                H,
                identifier='host',
                relationship='extension',
                related_type=case_type,
            )]
        )  # This case is in the middle

        C = CaseStructure(
            case_id='child',
            attrs={'create': True},
            indices=[CaseIndex(
                PH,
                identifier='parent',
                relationship='child',
                related_type=case_type,
            )]
        )
        # C and E are interchangable in their position in the hierarchy since
        # they point at the same case

        E = CaseStructure(
            case_id='extension',
            attrs={'create': True, 'owner_id': '-'},
            indices=[CaseIndex(
                PH,
                identifier='host',
                relationship='extension',
                related_type=case_type,
            )]
        )
        self.device.post_changes([C, E])

    def test_case_graph(self):
        cases = self.device.restore().cases
        self.assertEqual(
            ['host', 'parent_host', 'extension', 'child'],
            topological_sort_cases(cases)
        )

    def test_child_extensions(self):
        self.assertEqual(4, len(self.accessor.get_case_ids_in_domain()))

        explode_cases(self.project.name, self.user_id, 5)
        case_ids = self.accessor.get_case_ids_in_domain()
        self.assertEqual(20, len(case_ids))


@flag_enabled('NON_COMMTRACK_LEDGERS')
@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class ExplodeLedgersTest(BaseSyncTest):
    def setUp(self):
        super(ExplodeLedgersTest, self).setUp()
        self.case_accessor = CaseAccessors(self.project.name)
        self.ledger_accessor = LedgerAccessors(self.project.name)
        self._create_ledgers()

    def tearDown(self):
        delete_all_ledgers()
        delete_all_cases()
        delete_all_xforms()
        super(ExplodeLedgersTest, self).tearDown()

    def _create_ledgers(self):
        case_type = 'case'

        case1 = CaseStructure(
            case_id='case1',
            attrs={'create': True, 'case_type': case_type},
        )
        case2 = CaseStructure(
            case_id='case2',
            attrs={'create': True, 'case_type': case_type},
        )  # case2 will have no ledgers
        self.ledgers = {
            'icecream': Balance(
                entity_id=case1.case_id,
                date=datetime(2017, 11, 21, 0, 0, 0, 0),
                section_id='test',
                entry=Entry(id='icecream', quantity=4),
            ),
            'blondie': Balance(
                entity_id=case1.case_id,
                date=datetime(2017, 11, 21, 0, 0, 0, 0),
                section_id='test',
                entry=Entry(id='blondie', quantity=5),
            )
        }
        self.device.post_changes([case1, case2])
        self.device.post_changes(list(self.ledgers.values()))

    def test_explode_ledgers(self):
        explode_cases(self.project.name, self.user_id, 5)
        cases = self.case_accessor.iter_cases(self.case_accessor.get_case_ids_in_domain())
        for case in cases:
            ledger_values = {l.entry_id: l for l in self.ledger_accessor.get_ledger_values_for_case(case.case_id)}

            if case.case_id == 'case2' or case.get_case_property('cc_exploded_from') == 'case2':
                self.assertEqual(len(ledger_values), 0)
            else:
                self.assertEqual(len(ledger_values), len(self.ledgers))
                for id, balance in six.iteritems(self.ledgers):
                    self.assertEqual(ledger_values[id].balance, balance.entry.quantity)
                    self.assertEqual(ledger_values[id].entry_id, balance.entry.id)
