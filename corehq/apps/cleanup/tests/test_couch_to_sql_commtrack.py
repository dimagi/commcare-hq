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

    def _create_unsynced_couch(self):
        """
            Create a CommtrackConfig matching the one created by _create_unsynced_sql
        """
        couch = CommtrackConfig(
            domain='my_project',
            use_auto_emergency_levels=False,
            sync_consumption_fixtures=False,
            use_auto_consumption=False,
            individual_consumption_defaults=True,
            ota_restore_config=StockRestoreConfig(
                section_to_consumption_types={'s1': 'c1'},
                force_consumption_case_types=['type1'],
                use_dynamic_product_list=True,
            ),
            alert_config=AlertConfig(
                stock_out_facilities=True,
                stock_out_commodities=True,
                stock_out_rates=True,
                non_report=True,
            ),
            actions=[
                CommtrackActionConfig(
                    action='receipts',
                    subaction='sub-receipts',
                    _keyword='one',
                    caption='first action',
                ),
                CommtrackActionConfig(
                    action='receipts',
                    subaction='sub-receipts',
                    _keyword='two',
                    caption='second action',
                ),
            ],
            consumption_config=ConsumptionConfig(
                min_transactions=1,
                min_window=2,
                optimal_window=3,
                use_supply_point_type_default_consumption=True,
                exclude_invalid_periods=False,
            ),
            stock_levels_config=StockLevelsConfig(
                emergency_level=0.5,
                understock_threshold=1.5,
                overstock_threshold=3,
            )
        )
        couch.save(sync_to_sql=False)
        return couch

    def _create_unsynced_sql(self):
        """
            Create a SQLCommtrackConfig matching the one created by _create_unsynced_couch
        """
        sqlalertconfig = SQLAlertConfig(
            stock_out_facilities=True,
            stock_out_commodities=True,
            stock_out_rates=True,
            non_report=True,
        )
        sqlstockrestoreconfig = SQLStockRestoreConfig(
            section_to_consumption_types={'s1': 'c1'},
            force_consumption_case_types=['type1'],
            use_dynamic_product_list=True,
        )
        sqlconsumptionconfig = SQLConsumptionConfig(
            min_transactions=1,
            min_window=2,
            optimal_window=3,
            use_supply_point_type_default_consumption=True,
            exclude_invalid_periods=False,
        )
        sqlstocklevelsconfig = SQLStockLevelsConfig(
            emergency_level=0.5,
            understock_threshold=1.5,
            overstock_threshold=3,
        )
        sql = SQLCommtrackConfig(
            domain='my_project',
            use_auto_emergency_levels=False,
            sync_consumption_fixtures=False,
            use_auto_consumption=False,
            individual_consumption_defaults=True,
            sqlalertconfig=sqlalertconfig,
            sqlstockrestoreconfig=sqlstockrestoreconfig,
            sqlconsumptionconfig=sqlconsumptionconfig,
            sqlstocklevelsconfig=sqlstocklevelsconfig,
        )
        sql.save(sync_to_couch=False)   # save so that set_actions works

        sql.set_actions([
            SQLActionConfig(
                action='receipts',
                subaction='sub-receipts',
                _keyword='one',
                caption='first action',
            ),
            SQLActionConfig(
                action='receipts',
                subaction='sub-receipts',
                _keyword='two',
                caption='second action',
            ),
        ])
        sql.save(sync_to_couch=False)       # save actions

        # Save submodels
        sqlstockrestoreconfig.commtrack_config = sql
        sqlstockrestoreconfig.save()
        sqlalertconfig.commtrack_config = sql
        sqlalertconfig.save()
        sqlconsumptionconfig.commtrack_config = sql
        sqlconsumptionconfig.save()
        sqlstocklevelsconfig.commtrack_config = sql
        sqlstocklevelsconfig.save()

        return sql

    def _assert_sql(self, sql, use_auto_consumption=False, min_window=2, first_keyword='one'):
        """
            Assert that the given SQLCommtrackConfig matches the data used by
            _create_unsynced_sql and _create_unsynced_couch
        """
        self.assertEqual(sql.domain, "my_project")
        self.assertFalse(sql.use_auto_emergency_levels)
        self.assertFalse(sql.sync_consumption_fixtures)
        self.assertTrue(sql.use_auto_consumption == use_auto_consumption)
        self.assertTrue(sql.individual_consumption_defaults)

        self.assertTrue(sql.sqlalertconfig.stock_out_facilities)
        self.assertTrue(sql.sqlalertconfig.stock_out_commodities)
        self.assertTrue(sql.sqlalertconfig.stock_out_rates)
        self.assertTrue(sql.sqlalertconfig.non_report)

        self.assertEqual(sql.sqlstockrestoreconfig.section_to_consumption_types, {'s1': 'c1'})
        self.assertEqual(sql.sqlstockrestoreconfig.force_consumption_case_types, ['type1'])
        self.assertTrue(sql.sqlstockrestoreconfig.use_dynamic_product_list)

        self.assertEqual(sql.sqlconsumptionconfig.min_transactions, 1)
        self.assertEqual(sql.sqlconsumptionconfig.min_window, min_window)
        self.assertEqual(sql.sqlconsumptionconfig.optimal_window, 3)
        self.assertTrue(sql.sqlconsumptionconfig.use_supply_point_type_default_consumption)
        self.assertFalse(sql.sqlconsumptionconfig.exclude_invalid_periods)

        self.assertEqual(sql.sqlstocklevelsconfig.emergency_level, 0.5)
        self.assertEqual(sql.sqlstocklevelsconfig.understock_threshold, 1.5)
        self.assertEqual(sql.sqlstocklevelsconfig.overstock_threshold, 3)

        actions = sql.all_actions
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0].action, 'receipts')
        self.assertEqual(actions[0].subaction, 'sub-receipts')
        self.assertEqual(actions[0]._keyword, first_keyword)
        self.assertEqual(actions[0].caption, 'first action')
        self.assertEqual(actions[1].action, 'receipts')
        self.assertEqual(actions[1].subaction, 'sub-receipts')
        self.assertEqual(actions[1]._keyword, 'two')
        self.assertEqual(actions[1].caption, 'second action')

    def test_diff_identical(self):
        couch = self._create_unsynced_couch().to_json()
        sql = self._create_unsynced_sql()
        self.assertIsNone(Command.diff_couch_and_sql(couch, sql))

    def test_diff_top_level_attributes(self):
        couch = self._create_unsynced_couch().to_json()
        sql = self._create_unsynced_sql()
        couch['domain'] = 'other_project'
        couch['use_auto_emergency_levels'] = True
        self.assertEqual(Command.diff_couch_and_sql(couch, sql), "\n".join([
            "domain: couch value 'other_project' != sql value 'my_project'",
            "use_auto_emergency_levels: couch value 'True' != sql value 'False'",
        ]))

    def test_diff_submodel_attributes(self):
        couch = self._create_unsynced_couch().to_json()
        sql = self._create_unsynced_sql()
        couch['consumption_config']['min_window'] = 4
        couch['ota_restore_config']['force_consumption_case_types'] = ['type2']
        couch['ota_restore_config']['section_to_consumption_types'] = {'s1': 'c1', 's2': 'c2'}
        self.assertEqual(Command.diff_couch_and_sql(couch, sql), "\n".join([
            "min_window: couch value '4' != sql value '2'",
            "section_to_consumption_types: couch value '{'s1': 'c1', 's2': 'c2'}' != sql value '{'s1': 'c1'}'",
            "force_consumption_case_types: couch value '['type2']' != sql value '['type1']'",
        ]))

    def test_diff_remove_submodel(self):
        couch = self._create_unsynced_couch().to_json()
        sql = self._create_unsynced_sql()
        couch.pop('alert_config')
        self.assertEqual(Command.diff_couch_and_sql(couch, sql), "\n".join([
            "stock_out_facilities: couch value 'None' != sql value 'True'",
            "stock_out_commodities: couch value 'None' != sql value 'True'",
            "stock_out_rates: couch value 'None' != sql value 'True'",
            "non_report: couch value 'None' != sql value 'True'",
        ]))

    def test_diff_action_attributes(self):
        couch = self._create_unsynced_couch().to_json()
        sql = self._create_unsynced_sql()
        couch['actions'][0]['subaction'] = 'other-subaction'
        couch['actions'][1]['_keyword'] = 'dos'
        self.assertEqual(Command.diff_couch_and_sql(couch, sql), "\n".join([
            "subaction: couch value 'other-subaction' != sql value 'sub-receipts'",
            "_keyword: couch value 'dos' != sql value 'two'",
        ]))

    def test_diff_action_order(self):
        couch = self._create_unsynced_couch().to_json()
        sql = self._create_unsynced_sql()
        (action1, action2) = couch['actions']
        couch['actions'] = [action2, action1]
        self.assertEqual(Command.diff_couch_and_sql(couch, sql), "\n".join([
            "_keyword: couch value 'two' != sql value 'one'",
            "caption: couch value 'second action' != sql value 'first action'",
            "_keyword: couch value 'one' != sql value 'two'",
            "caption: couch value 'first action' != sql value 'second action'",
        ]))

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

    def test_sync_to_couch(self):
        sql = self._create_unsynced_sql()
        sql.save()
        actual = self.db.get(sql.couch_id)
        expected = self._create_unsynced_couch().to_json()
        actual.pop('_id')
        actual.pop('_rev')
        expected.pop('_id')
        expected.pop('_rev')
        self.assertEqual(actual, expected)

    def test_sync_to_sql(self):
        couch = self._create_unsynced_couch()
        couch.save()
        actual = SQLCommtrackConfig.objects.get(couch_id=couch._id)
        self._assert_sql(actual)

    def test_migration(self):
        couch = self._create_unsynced_couch()
        couch.save()

        # Create any sql objects that didn't exist pre-migration
        call_command('populate_commtrackconfig')
        actual = SQLCommtrackConfig.objects.get(couch_id=couch._id)
        self._assert_sql(actual)

        # Update any pre-existing sql objects
        couch['use_auto_consumption'] = True
        couch['consumption_config']['min_window'] = 3
        couch['actions'][0]['_keyword'] = 'uno'
        couch.save(sync_to_sql=False)
        call_command('populate_commtrackconfig')
        actual = SQLCommtrackConfig.objects.get(couch_id=couch._id)
        self._assert_sql(actual, use_auto_consumption=True, min_window=3, first_keyword='uno')
