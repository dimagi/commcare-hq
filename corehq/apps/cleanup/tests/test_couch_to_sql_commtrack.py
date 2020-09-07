from django.core.management import call_command
from django.test import TestCase

from corehq.apps.commtrack.management.commands.populate_commtrackconfig import Command
from corehq.apps.commtrack.models import (
    CommtrackConfig,
    AlertConfig,
    CommtrackActionConfig,
    ConsumptionConfig,
    StockLevelsConfig,
    StockRestoreConfig,
    SQLCommtrackConfig,
    SQLActionConfig,
    SQLAlertConfig,
    SQLConsumptionConfig,
    SQLStockLevelsConfig,
    SQLStockRestoreConfig,
)
from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types


class TestCouchToSQLCommtrackConfig(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db = CommtrackConfig.get_db()

    def tearDown(self):
        SQLCommtrackConfig.objects.all().delete()
        for doc in get_all_docs_with_doc_types(self.db, ['CommtrackConfig']):
            CommtrackConfig.wrap(doc).delete()
        super().tearDown()

    def test_wrap_action_config(self):
        # action_type is an old alias for action
        self.assertEqual(Command._wrap_action_config({
            'action_type': 'receipts',
            'subaction': 'some subaction',
            '_keyword': 'some word',
            'caption': 'some caption',
        }), {
            'action': 'receipts',
            'subaction': 'some subaction',
            '_keyword': 'some word',
            'caption': 'some caption',
        })

        # actions named 'lost' get 'loss' subactions
        self.assertEqual(Command._wrap_action_config({
            'action': 'consume',
            'name': 'lost',
            'subaction': 'some subaction',
            '_keyword': 'some word',
            'caption': 'some caption',
        }), {
            'action': 'consume',
            'subaction': 'loss',
            '_keyword': 'some word',
            'caption': 'some caption',
        })

    def test_wrap_stock_restore_config(self):
        # force_to_consumption_case_types is an old alias for force_consumption_case_types
        self.assertEqual(Command._wrap_stock_restore_config({
            'force_to_consumption_case_types': [1],
            'force_consumption_case_types': [],
            'section_to_consumption_types': {},
            'use_dynamic_product_list': True,
        }), {
            'force_consumption_case_types': [1],
            'section_to_consumption_types': {},
            'use_dynamic_product_list': True,
        })

        # Don't overwrite if there's already a value in force_consumption_case_types
        self.assertEqual(Command._wrap_stock_restore_config({
            'force_to_consumption_case_types': [1],
            'force_consumption_case_types': [2],
            'section_to_consumption_types': {},
            'use_dynamic_product_list': True,
        }), {
            'force_to_consumption_case_types': [1],
            'force_consumption_case_types': [2],
            'section_to_consumption_types': {},
            'use_dynamic_product_list': True,
        })
