from __future__ import absolute_import
from corehq.apps.commtrack.tests.util import get_single_balance_block
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.products.models import Product
from corehq.form_processor.models import LedgerValue
from custom.icds.case_relationships import (
    child_person_case_from_tasks_case,
    ccs_record_case_from_tasks_case,
)
from custom.icds.rules.immunization import (
    get_immunization_products,
    get_tasks_case_immunization_ledger_values,
    get_immunization_date,
    get_immunization_anchor_date,
    get_map,
    calculate_immunization_window,
    immunization_is_due,
)
from custom.icds.tests.base import BaseICDSTest
from datetime import date
from mock import patch


class ImmunizationUtilTestCase(BaseICDSTest):
    domain = 'icds-immunization-util'

    @classmethod
    def setUpClass(cls):
        super(ImmunizationUtilTestCase, cls).setUpClass()
        cls.ccs_record = cls.create_case(
            'ccs_record',
            update={'edd': '2017-08-01'}
        )
        cls.tasks_pregnancy = cls.create_case(
            'tasks',
            parent_case_id=cls.ccs_record.case_id,
            parent_case_type='ccs_record',
            parent_identifier='parent',
            parent_relationship='extension',
            update={'tasks_type': 'pregnancy', 'schedule_flag': 'tt_norm'}
        )

        cls.person_child = cls.create_case(
            'person',
            update={'dob': '2017-08-10'}
        )
        cls.child_health = cls.create_case(
            'child_health',
            parent_case_id=cls.person_child.case_id,
            parent_case_type='person',
            parent_identifier='parent',
            parent_relationship='extension'
        )
        cls.tasks_child = cls.create_case(
            'tasks',
            parent_case_id=cls.child_health.case_id,
            parent_case_type='child_health',
            parent_identifier='parent',
            parent_relationship='extension',
            update={'tasks_type': 'child'}
        )

        cls.lone_tasks_case = cls.create_case('tasks', update={'tasks_type': 'child'})

        cls.dpt2 = cls.create_product('2g_dpt_2', 'child', '70', '730', '1g_dpt_1', '28')
        cls.dpt3 = cls.create_product('3g_dpt_3', 'child', '98', '730', '2g_dpt_2', '28')

        cls.tt1 = cls.create_product('tt_1', 'pregnancy', '-274', '180', schedule_flag='tt_norm')
        cls.ttbooster = cls.create_product('tt_booster', 'pregnancy', '-1096', '180', schedule_flag='tt_boost')
        cls.anc1 = cls.create_product('anc_1', 'pregnancy', '-274', '180')
        cls.anc2 = cls.create_product('anc_2', 'pregnancy', '-274', '180', 'anc_1', '30')

        submit_case_blocks(
            get_single_balance_block(cls.lone_tasks_case.case_id, cls.dpt2.get_id, 17400, section_id='immuns'),
            cls.domain
        )

    @classmethod
    def create_product(cls, code, schedule, valid, expires, predecessor_id='', days_after_previous='',
            schedule_flag=''):
        p = Product(
            domain=cls.domain,
            name=code,
            code=code,
            product_data={
                'schedule': schedule,
                'valid': valid,
                'expires': expires,
                'predecessor_id': predecessor_id,
                'days_after_previous': days_after_previous,
                'schedule_flag': schedule_flag,
            }
        )
        p.save()
        return p

    def test_get_immunization_products(self):
        self.assertItemsEqual(
            [p.product_id for p in get_immunization_products(self.domain, 'child')],
            [self.dpt2.get_id, self.dpt3.get_id]
        )

        self.assertItemsEqual(
            [p.product_id for p in get_immunization_products(self.domain, 'pregnancy')],
            [self.tt1.get_id, self.ttbooster.get_id, self.anc1.get_id, self.anc2.get_id]
        )

    def test_ledger_values(self):
        [ledger_value] = get_tasks_case_immunization_ledger_values(self.lone_tasks_case)
        self.assertEqual(ledger_value.case_id, self.lone_tasks_case.case_id)
        self.assertEqual(ledger_value.entry_id, self.dpt2.get_id)
        self.assertEqual(ledger_value.section_id, 'immuns')
        self.assertEqual(ledger_value.balance, 17400)

        self.assertEqual(get_immunization_date(ledger_value), date(2017, 8, 22))

    def test_case_relationships(self):
        self.assertEqual(
            child_person_case_from_tasks_case(self.tasks_child).case_id,
            self.person_child.case_id
        )

        self.assertEqual(
            ccs_record_case_from_tasks_case(self.tasks_pregnancy).case_id,
            self.ccs_record.case_id
        )

    def test_get_immunization_anchor_date(self):
        self.assertEqual(
            get_immunization_anchor_date(self.tasks_child),
            date(2017, 8, 10)
        )

        self.assertEqual(
            get_immunization_anchor_date(self.tasks_pregnancy),
            date(2017, 8, 1)
        )

    def test_calculate_immunization_window(self):
        pregnancy_products = get_immunization_products(self.domain, 'pregnancy')
        child_products = get_immunization_products(self.domain, 'child')

        self.assertEqual(
            calculate_immunization_window(
                self.tasks_pregnancy,
                date(2017, 8, 1),
                get_map(pregnancy_products, 'code')['anc_1'],
                pregnancy_products,
                []
            ),
            (date(2016, 10, 31), date(2018, 1, 28))
        )

        self.assertEqual(
            calculate_immunization_window(
                self.tasks_child,
                date(2017, 8, 1),
                get_map(child_products, 'code')['3g_dpt_3'],
                child_products,
                []
            ),
            (None, date(2019, 8, 1))
        )

        self.assertEqual(
            calculate_immunization_window(
                self.tasks_child,
                date(2017, 8, 1),
                get_map(child_products, 'code')['3g_dpt_3'],
                child_products,
                [LedgerValue(entry_id=self.dpt2.get_id, balance=17390)]
            ),
            (date(2017, 11, 7), date(2019, 8, 1))
        )

        self.assertEqual(
            calculate_immunization_window(
                self.tasks_child,
                date(2017, 8, 1),
                get_map(child_products, 'code')['3g_dpt_3'],
                child_products,
                [LedgerValue(entry_id=self.dpt2.get_id, balance=17501)]
            ),
            (date(2017, 12, 29), date(2019, 8, 1))
        )

    @patch('custom.icds.rules.immunization.todays_date')
    def test_immunization_is_due(self, todays_date):
        pregnancy_products = get_immunization_products(self.domain, 'pregnancy')
        child_products = get_immunization_products(self.domain, 'child')

        # Immunization is due when it has a predecessor which is completed and its date range is valid
        todays_date.return_value = date(2018, 1, 1)
        self.assertTrue(
            immunization_is_due(
                self.tasks_child,
                date(2017, 8, 1),
                get_map(child_products, 'code')['3g_dpt_3'],
                child_products,
                [LedgerValue(entry_id=self.dpt2.get_id, balance=17501)]
            )
        )

        # Immunization is not due when it has a predecessor and its predecessor is not completed
        todays_date.return_value = date(2018, 1, 1)
        self.assertFalse(
            immunization_is_due(
                self.tasks_child,
                date(2017, 8, 1),
                get_map(child_products, 'code')['3g_dpt_3'],
                child_products,
                []
            )
        )

        # Immunization is due when it has a schedule_flag which is applied to the tasks case
        # and its date range is valid
        todays_date.return_value = date(2017, 9, 1)
        self.assertTrue(
            immunization_is_due(
                self.tasks_pregnancy,
                date(2017, 8, 1),
                get_map(pregnancy_products, 'code')['tt_1'],
                pregnancy_products,
                []
            )
        )

        # Immunization is not due when it has a schedule_flag which is not applied to the tasks case
        # even though its date range is valid
        todays_date.return_value = date(2017, 9, 1)
        self.assertFalse(
            immunization_is_due(
                self.tasks_pregnancy,
                date(2017, 8, 1),
                get_map(pregnancy_products, 'code')['tt_booster'],
                pregnancy_products,
                []
            )
        )

        # Immunization is not due when its date range is not valid
        todays_date.return_value = date(2020, 9, 1)
        self.assertFalse(
            immunization_is_due(
                self.tasks_pregnancy,
                date(2017, 8, 1),
                get_map(pregnancy_products, 'code')['tt_1'],
                pregnancy_products,
                []
            )
        )

        # Immunization is not due when it has already been completed
        todays_date.return_value = date(2017, 9, 1)
        self.assertFalse(
            immunization_is_due(
                self.tasks_pregnancy,
                date(2017, 8, 1),
                get_map(pregnancy_products, 'code')['tt_1'],
                pregnancy_products,
                [LedgerValue(entry_id=self.tt1.get_id, balance=17390)]
            )
        )
