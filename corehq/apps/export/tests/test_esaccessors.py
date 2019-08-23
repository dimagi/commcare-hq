from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

from django.test import TestCase, SimpleTestCase

from casexml.apps.case.mock import CaseFactory

from corehq.apps.commtrack.helpers import make_product
from corehq.apps.commtrack.tests.util import get_single_balance_block
from corehq.apps.export.esaccessors import get_ledger_section_entry_combinations, get_groups_user_ids
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.elastic import send_to_elasticsearch, get_es_new
from corehq.form_processor.models import LedgerValue
from corehq.form_processor.tests.utils import FormProcessorTestUtils, run_with_all_backends
from corehq.pillows.mappings.ledger_mapping import LEDGER_INDEX_INFO
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.apps.groups.models import Group
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index_and_mapping


class TestExportESAccessors(TestCase):
    domain = 'export-es-domain'

    @classmethod
    def setUpClass(cls):
        super(TestExportESAccessors, cls).setUpClass()
        cls.product_a = make_product(cls.domain, 'A Product', 'product_a')
        cls.product_b = make_product(cls.domain, 'B Product', 'product_b')
        cls.product_c = make_product(cls.domain, 'C Product', 'product_c')

        cls.expected_combos = {
            ('stock', cls.product_a.get_id),
            ('stock', cls.product_b.get_id),
            ('consumption', cls.product_a.get_id),
            ('consumption', cls.product_c.get_id),
        }

    @classmethod
    def tearDownClass(cls):
        cls.product_a.delete()
        cls.product_b.delete()
        cls.product_c.delete()
        super(TestExportESAccessors, cls).tearDownClass()

    def setUp(self):
        super(TestExportESAccessors, self).setUp()
        factory = CaseFactory(domain=self.domain)
        self.case_one = factory.create_case()

        for section, entry in self.expected_combos:
            submit_case_blocks(
                [get_single_balance_block(
                    case_id=self.case_one.case_id,
                    section_id=section,
                    product_id=entry,
                    quantity=20,
                )],
                self.domain
            )

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        super(TestExportESAccessors, self).tearDown()

    @run_with_all_backends
    def test_get_ledger_section_entry_combinations(self):
        combos = get_ledger_section_entry_combinations(self.domain)
        self.assertEqual(
            self.expected_combos,
            {(combo.section_id, combo.entry_id) for combo in combos}
        )


class TestGroupUserIds(SimpleTestCase):
    domain = 'group-es-domain'

    @classmethod
    def setUpClass(cls):
        super(TestGroupUserIds, cls).setUpClass()
        ensure_index_deleted(GROUP_INDEX_INFO.index)
        cls.es = get_es_new()
        initialize_index_and_mapping(cls.es, GROUP_INDEX_INFO)
        cls.es.indices.refresh(GROUP_INDEX_INFO.index)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(GROUP_INDEX_INFO.index)
        super(TestGroupUserIds, cls).tearDownClass()

    def _send_group_to_es(self, _id=None, users=None):
        group = Group(
            domain=self.domain,
            name='narcos',
            users=users or [],
            case_sharing=False,
            reporting=True,
            _id=_id or uuid.uuid4().hex,
        )
        send_to_elasticsearch('groups', group.to_json())
        self.es.indices.refresh(GROUP_INDEX_INFO.index)
        return group

    def test_one_group_to_users(self):
        group1 = self._send_group_to_es(users=['billy', 'joel'])

        user_ids = get_groups_user_ids([group1._id])
        self.assertEqual(set(user_ids), set(['billy', 'joel']))

    def test_multiple_groups_to_users(self):
        group1 = self._send_group_to_es(users=['billy', 'joel'])
        group2 = self._send_group_to_es(users=['eric', 'clapton'])

        user_ids = get_groups_user_ids([group1._id, group2._id])
        self.assertEqual(set(user_ids), set(['billy', 'joel', 'eric', 'clapton']))

    def test_one_user_in_group(self):
        group1 = self._send_group_to_es(users=['billy'])

        user_ids = get_groups_user_ids([group1._id])
        self.assertEqual(set(user_ids), set(['billy']))
