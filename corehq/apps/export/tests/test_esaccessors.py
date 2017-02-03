import uuid

from django.test import TestCase, SimpleTestCase

from corehq.apps.export.esaccessors import get_ledger_section_entry_combinations, get_groups_user_ids
from corehq.elastic import send_to_elasticsearch, get_es_new
from corehq.form_processor.models import LedgerValue
from corehq.pillows.mappings.ledger_mapping import LEDGER_INDEX_INFO
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.apps.groups.models import Group
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index_and_mapping


class TestExportESAccessors(TestCase):
    domain = 'export-es-domain'

    @classmethod
    def setUpClass(cls):
        ensure_index_deleted(LEDGER_INDEX_INFO.index)
        es = get_es_new()
        initialize_index_and_mapping(es, LEDGER_INDEX_INFO)

        cls.expected_combos = {
            ('stock', 'product_a'),
            ('stock', 'product_b'),
            ('consumption', 'product_a'),
            ('consumption', 'product_c'),
        }
        for section, entry in cls.expected_combos:
            ledger = LedgerValue(
                domain=cls.domain,
                case_id=uuid.uuid4().hex,
                section_id=section,
                entry_id=entry,
            )
            ledger_json = ledger.to_json(include_location_id=False)
            ledger_json['_id'] = ledger.ledger_reference.as_id()
            send_to_elasticsearch('ledgers', doc=ledger_json)

        es.indices.refresh(LEDGER_INDEX_INFO.index)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(LEDGER_INDEX_INFO.index)

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
        ensure_index_deleted(GROUP_INDEX_INFO.index)
        cls.es = get_es_new()
        initialize_index_and_mapping(cls.es, GROUP_INDEX_INFO)
        cls.es.indices.refresh(GROUP_INDEX_INFO.index)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(GROUP_INDEX_INFO.index)

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
