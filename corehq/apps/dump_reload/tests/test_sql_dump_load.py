import functools
import inspect
import json
import uuid
from StringIO import StringIO
from collections import Counter

from django.contrib.admin.utils import NestedObjects
from django.core import serializers
from django.db.models.signals import post_save
from django.test import TestCase
from django.test.utils import override_settings

from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.apps.commtrack.helpers import make_product
from corehq.apps.commtrack.tests.util import get_single_balance_block
from corehq.apps.domain.models import Domain
from corehq.apps.dump_reload.sql import SqlDataLoader, SqlDataDumper
from corehq.apps.dump_reload.sql.dump import get_model_domain_filters, get_objects_to_dump
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.products.models import SQLProduct
from corehq.apps.tzmigration.models import TimezoneMigrationProgress
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.form_processor.models import (
    XFormInstanceSQL, XFormAttachmentSQL, CommCareCaseSQL, CommCareCaseIndexSQL, CaseTransaction,
    LedgerValue, LedgerTransaction)
from corehq.form_processor.tests.utils import FormProcessorTestUtils, create_form_for_test


def register_cleanup(test, models, domain):
    test.addCleanup(functools.partial(delete_sql_data, test, models, domain))


@override_settings(ALLOW_FORM_PROCESSING_QUERIES=True)
def delete_sql_data(test, models, domain):
    for model in models:
        filters = get_model_domain_filters(model, domain)
        for filter in filters:
            collector = NestedObjects(using='default')
            collector.collect(model.objects.filter(filter))
            collector.delete()
            test.assertFalse(model.objects.filter(filter).exists(), model)


class BaseDumpLoadTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(BaseDumpLoadTest, cls).setUpClass()
        cls.domain_name = uuid.uuid4().hex
        cls.domain = Domain(name=cls.domain_name)
        cls.domain.save()

        cls.default_objects_counts = Counter({
            TimezoneMigrationProgress: 1
        })

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(BaseDumpLoadTest, cls).tearDownClass()

    @override_settings(ALLOW_FORM_PROCESSING_QUERIES=True)
    def _dump_and_load(self, expected_object_counts):
        expected_object_counts.update(self.default_objects_counts)

        models = list(expected_object_counts)

        output_stream = StringIO()
        SqlDataDumper(self.domain_name, []).dump(output_stream)

        delete_sql_data(self, models, self.domain_name)

        # make sure that there's no data left in the DB
        objects_remaining = list(get_objects_to_dump(self.domain_name, []))
        object_classes = [obj.__class__.__name__ for obj in objects_remaining]
        counts = Counter(object_classes)
        self.assertEqual([], objects_remaining, 'Not all data deleted: {}'.format(counts))

        dump_output = output_stream.getvalue()
        dump_lines = [line.strip() for line in dump_output.split('\n') if line.strip()]
        total_object_count, loaded_model_counts = SqlDataLoader().load_objects(dump_lines)

        expected_model_counts = _normalize_object_counter(expected_object_counts)
        actual_model_counts = Counter([json.loads(line)['model'] for line in dump_lines])
        expected_total_objects = sum(expected_object_counts.values())
        self.assertDictEqual(expected_model_counts, actual_model_counts)
        self.assertEqual(expected_total_objects, sum(loaded_model_counts.values()))
        self.assertEqual(expected_total_objects, total_object_count)

        return dump_lines

    def _check_signals_handle_raw(self, models):
        """Ensure that any post_save signal handlers have been updated
        to handle 'raw' calls."""
        whitelist_receivers = [
            'django_digest.models._post_save_persist_partial_digests'
        ]
        post_save_receivers = post_save.receivers
        for model in models:
            target_id = id(model)
            for receiver in post_save_receivers:
                if receiver[0][1] == target_id:
                    receiver_fn = receiver[1]()
                    receiver_path = receiver_fn.__module__ + '.' + receiver_fn.__name__
                    if receiver_path in whitelist_receivers:
                        continue
                    args = inspect.getargspec(receiver_fn).args
                    message = 'Signal handler "{}" for model "{}" missing raw arg'.format(
                        receiver_fn, model
                    )
                    self.assertIn('raw', args, message)


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestSQLDumpLoadShardedModels(BaseDumpLoadTest):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(TestSQLDumpLoadShardedModels, cls).setUpClass()
        cls.factory = CaseFactory(domain=cls.domain_name)
        cls.form_accessors = FormAccessors(cls.domain_name)
        cls.case_accessors = CaseAccessors(cls.domain_name)
        cls.product = make_product(cls.domain_name, 'A Product', 'prodcode_a')
        cls.default_objects_counts.update({SQLProduct: 1})

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain_name)
        super(TestSQLDumpLoadShardedModels, cls).tearDownClass()

    def test_dump_laod_form(self):
        expected_object_counts = Counter({
            XFormInstanceSQL: 2,
            XFormAttachmentSQL: 2
        })
        register_cleanup(self, list(expected_object_counts), self.domain_name)

        pre_forms = [
            create_form_for_test(self.domain_name),
            create_form_for_test(self.domain_name)
        ]
        self._dump_and_load(expected_object_counts)

        form_ids = self.form_accessors.get_all_form_ids_in_domain('XFormInstance')
        self.assertEqual(set(form_ids), set(form.form_id for form in pre_forms))

        for pre_form in pre_forms:
            post_form = self.form_accessors.get_form(pre_form.form_id)
            self.assertDictEqual(pre_form.to_json(), post_form.to_json())

    def test_sql_dump_load_case(self):
        expected_object_counts = Counter({
            XFormInstanceSQL: 2,
            XFormAttachmentSQL: 2,
            CommCareCaseSQL: 2,
            CaseTransaction: 3,
            CommCareCaseIndexSQL: 1

        })
        register_cleanup(self, list(expected_object_counts), self.domain_name)

        pre_cases = self.factory.create_or_update_case(
            CaseStructure(
                attrs={'case_name': 'child', 'update': {'age': 3, 'diabetic': False}},
                indices=[
                    CaseIndex(CaseStructure(attrs={'case_name': 'parent', 'update': {'age': 42}})),
                ]
            )
        )
        pre_cases[0] = self.factory.create_or_update_case(CaseStructure(
            case_id=pre_cases[0].case_id,
            attrs={'external_id': 'billie jean', 'update': {'name': 'Billie Jean'}}
        ))[0]

        self._dump_and_load(expected_object_counts)

        case_ids = self.case_accessors.get_case_ids_in_domain()
        self.assertEqual(set(case_ids), set(case.case_id for case in pre_cases))
        for pre_case in pre_cases:
            post_case = self.case_accessors.get_case(pre_case.case_id)
            self.assertDictEqual(pre_case.to_json(), post_case.to_json())

    def test_ledgers(self):
        expected_object_counts = Counter({
            XFormInstanceSQL: 3,
            XFormAttachmentSQL: 3,
            CommCareCaseSQL: 1,
            CaseTransaction: 3,
            LedgerValue: 1,
            LedgerTransaction: 2

        })
        register_cleanup(self, list(expected_object_counts), self.domain_name)

        case = self.factory.create_case()
        submit_case_blocks([
            get_single_balance_block(case.case_id, self.product._id, 10)
        ], self.domain_name)
        submit_case_blocks([
            get_single_balance_block(case.case_id, self.product._id, 5)
        ], self.domain_name)

        pre_ledger_values = LedgerAccessorSQL.get_ledger_values_for_case(case.case_id)
        pre_ledger_transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(case.case_id)
        self.assertEqual(1, len(pre_ledger_values))
        self.assertEqual(2, len(pre_ledger_transactions))

        self._dump_and_load(expected_object_counts)

        post_ledger_values = LedgerAccessorSQL.get_ledger_values_for_case(case.case_id)
        post_ledger_transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(case.case_id)
        self.assertEqual(1, len(post_ledger_values))
        self.assertEqual(2, len(post_ledger_transactions))
        self.assertEqual(pre_ledger_values[0].ledger_reference, post_ledger_values[0].ledger_reference)
        self.assertDictEqual(pre_ledger_values[0].to_json(), post_ledger_values[0].to_json())

        pre_ledger_transactions = sorted(pre_ledger_transactions, key=lambda t: t.pk)
        post_ledger_transactions = sorted(post_ledger_transactions, key=lambda t: t.pk)
        for pre, post in zip(pre_ledger_transactions, post_ledger_transactions):
            self.assertEqual(str(pre), str(post))


class TestSQLDumpLoad(BaseDumpLoadTest):
    def assertModelsEqual(self, pre_models, post_models):
        for pre, post in zip(pre_models, post_models):
            pre_json = serializers.serialize('python', [pre])[0]
            post_json = serializers.serialize('python', [post])[0]
            self.assertDictEqual(pre_json, post_json)

    def test_case_search_config(self):
        from corehq.apps.case_search.models import CaseSearchConfig, CaseSearchConfigJSON
        expected_object_counts = Counter({
            CaseSearchConfig: 1,
        })
        register_cleanup(self, list(expected_object_counts), self.domain_name)

        pre_config, created = CaseSearchConfig.objects.get_or_create(pk=self.domain_name)
        pre_config.enabled = True
        fuzzies = CaseSearchConfigJSON()
        fuzzies.add_fuzzy_properties('dog', ['breed', 'color'])
        fuzzies.add_fuzzy_properties('owner', ['name'])
        pre_config.config = fuzzies
        pre_config.save()

        self._dump_and_load(expected_object_counts)

        post_config = CaseSearchConfig.objects.get(domain=self.domain_name)
        self.assertTrue(post_config.enabled)
        self.assertDictEqual(pre_config.config.to_json(), post_config.config.to_json())

    def test_auto_case_update_rules(self):
        from corehq.apps.data_interfaces.models import (
            AutomaticUpdateRule, AutomaticUpdateRuleCriteria, AutomaticUpdateAction
        )
        expected_object_counts = Counter({
            AutomaticUpdateRule: 1,
            AutomaticUpdateRuleCriteria: 1,
            AutomaticUpdateAction: 2,
        })
        register_cleanup(self, list(expected_object_counts), self.domain_name)

        pre_rule = AutomaticUpdateRule(
            domain=self.domain_name,
            name='test-rule',
            case_type='test-case-type',
            active=True,
            server_modified_boundary=30,
        )
        pre_rule.save()
        pre_criteria = AutomaticUpdateRuleCriteria.objects.create(
            property_name='last_visit_date',
            property_value='30',
            match_type=AutomaticUpdateRuleCriteria.MATCH_DAYS_AFTER,
            rule=pre_rule,
        )
        pre_action_update = AutomaticUpdateAction.objects.create(
            action=AutomaticUpdateAction.ACTION_UPDATE,
            property_name='update_flag',
            property_value='Y',
            rule=pre_rule,
        )
        pre_action_close = AutomaticUpdateAction.objects.create(
            action=AutomaticUpdateAction.ACTION_CLOSE,
            rule=pre_rule,
        )

        self._dump_and_load(expected_object_counts)

        post_rule = AutomaticUpdateRule.objects.get(pk=pre_rule.pk)
        post_criteria = AutomaticUpdateRuleCriteria.objects.get(pk=pre_criteria.pk)
        post_action_update = AutomaticUpdateAction.objects.get(pk=pre_action_update.pk)
        post_action_close = AutomaticUpdateAction.objects.get(pk=pre_action_close.pk)

        self.assertModelsEqual(
            [pre_rule, pre_criteria, pre_action_update, pre_action_close],
            [post_rule, post_criteria, post_action_update, post_action_close]
        )

    def test_users(self):
        from corehq.apps.users.models import CommCareUser
        from corehq.apps.users.models import WebUser
        from django.contrib.auth.models import User

        expected_object_counts = Counter({User: 3})
        register_cleanup(self, list(expected_object_counts), self.domain_name)

        ccuser_1 = CommCareUser.create(
            domain=self.domain_name,
            username='user_1',
            password='secret',
            email='email@example.com',
        )
        ccuser_2 = CommCareUser.create(
            domain=self.domain_name,
            username='user_2',
            password='secret',
            email='email1@example.com',
        )
        web_user = WebUser.create(
            domain=self.domain_name,
            username='webuser_t1',
            password='secret',
            email='webuser@example.com',
        )
        self.addCleanup(ccuser_1.delete)
        self.addCleanup(ccuser_2.delete)
        self.addCleanup(web_user.delete)

        self._dump_and_load(expected_object_counts)

    def test_device_logs(self):
        from corehq.apps.receiverwrapper.util import submit_form_locally
        from phonelog.models import DeviceReportEntry, ForceCloseEntry, UserEntry, UserErrorEntry
        from corehq.apps.users.models import CommCareUser
        from django.contrib.auth.models import User

        expected_object_counts = Counter({
            User: 1,
            DeviceReportEntry: 7,
            UserEntry: 1,
            UserErrorEntry: 2,
            ForceCloseEntry: 1
        })
        register_cleanup(self, list(expected_object_counts), self.domain_name)

        user = CommCareUser.create(
            domain=self.domain_name,
            username='user_1',
            password='secret',
            email='email@example.com',
            uuid='428d454aa9abc74e1964e16d3565d6b6'  # match ID in devicelog.xml
        )
        self.addCleanup(user.delete)

        with open('corehq/ex-submodules/couchforms/tests/data/devicelogs/devicelog.xml') as f:
            xml = f.read()
        submit_form_locally(xml, self.domain_name)

        self._dump_and_load(expected_object_counts)

    def test_demo_user_restore(self):
        from corehq.apps.users.models import CommCareUser
        from corehq.apps.ota.models import DemoUserRestore
        from django.contrib.auth.models import User

        expected_object_counts = Counter({
            User: 1,
            DemoUserRestore: 1
        })
        register_cleanup(self, list(expected_object_counts), self.domain_name)

        user_id = uuid.uuid4().hex
        user = CommCareUser.create(
            domain=self.domain_name,
            username='user_1',
            password='secret',
            email='email@example.com',
            uuid=user_id
        )
        self.addCleanup(user.delete)

        DemoUserRestore(
            demo_user_id=user_id,
            restore_blob_id=uuid.uuid4().hex,
            content_length=1027,
            restore_comment="Test migrate demo user restore"
        ).save()

        self._dump_and_load(expected_object_counts)

    def test_products(self):
        from corehq.apps.products.models import SQLProduct
        expected_object_counts = Counter({SQLProduct: 3})
        register_cleanup(self, list(expected_object_counts), self.domain_name)

        p1 = SQLProduct.objects.create(domain=self.domain_name, product_id='test1', name='test1')
        p2 = SQLProduct.objects.create(domain=self.domain_name, product_id='test2', name='test2')
        parchived = SQLProduct.objects.create(domain=self.domain_name, product_id='test3', name='test3', is_archived=True)

        self._dump_and_load(expected_object_counts)

        self.assertEqual(2, SQLProduct.active_objects.filter(domain=self.domain_name).count())
        all_active = SQLProduct.active_objects.filter(domain=self.domain_name).all()
        self.assertTrue(p1 in all_active)
        self.assertTrue(p2 in all_active)
        self.assertTrue(parchived not in all_active)

    def test_location_type(self):
        from corehq.apps.locations.models import LocationType
        from corehq.apps.locations.tests.test_location_types import make_loc_type
        expected_object_counts = Counter({LocationType: 7})
        register_cleanup(self, list(expected_object_counts), self.domain_name)

        state = make_loc_type('state', domain=self.domain_name)

        district = make_loc_type('district', state, domain=self.domain_name)
        section = make_loc_type('section', district, domain=self.domain_name)
        block = make_loc_type('block', district, domain=self.domain_name)
        center = make_loc_type('center', block, domain=self.domain_name)

        county = make_loc_type('county', state, domain=self.domain_name)
        city = make_loc_type('city', county, domain=self.domain_name)

        self._dump_and_load(expected_object_counts)

        hierarchy = LocationType.objects.full_hierarchy(self.domain_name)
        desired_hierarchy = {
            state.id: (
                state,
                {
                    district.id: (
                        district,
                        {
                            section.id: (section, {}),
                            block.id: (block, {
                                center.id: (center, {}),
                            }),
                        },
                    ),
                    county.id: (
                        county,
                        {city.id: (city, {})},
                    ),
                },
            ),
        }
        self.assertEqual(hierarchy, desired_hierarchy)

    def test_location(self):
        from corehq.apps.locations.models import LocationType, SQLLocation
        from corehq.apps.locations.tests.util import setup_locations_and_types
        expected_object_counts = Counter({LocationType: 3, SQLLocation: 11})
        register_cleanup(self, list(expected_object_counts), self.domain_name)

        location_type_names = ['province', 'district', 'city']
        location_structure = [
            ('Western Cape', [
                ('Cape Winelands', [
                    ('Stellenbosch', []),
                    ('Paarl', []),
                ]),
                ('Cape Town', [
                    ('Cape Town City', []),
                ])
            ]),
            ('Gauteng', [
                ('Ekurhuleni ', [
                    ('Alberton', []),
                    ('Benoni', []),
                    ('Springs', []),
                ]),
            ]),
        ]

        location_types, locations = setup_locations_and_types(
            self.domain_name,
            location_type_names,
            [],
            location_structure,
        )

        self._dump_and_load(expected_object_counts)

        names = ['Cape Winelands', 'Paarl', 'Cape Town']
        location_ids = [locations[name].location_id for name in names]
        result = SQLLocation.objects.get_locations_and_children(location_ids)
        self.assertItemsEqual(
            [loc.name for loc in result],
            ['Cape Winelands', 'Stellenbosch', 'Paarl', 'Cape Town', 'Cape Town City']
        )

        result = SQLLocation.objects.get_locations_and_children([locations['Gauteng'].location_id])
        self.assertItemsEqual(
            [loc.name for loc in result],
            ['Gauteng', 'Ekurhuleni ', 'Alberton', 'Benoni', 'Springs']
        )


def _normalize_object_counter(counter):
    """Converts a <Model Class> keyed counter to an model label keyed counter"""
    def _model_class_to_label(model_class):
        return '{}.{}'.format(model_class._meta.app_label, model_class.__name__).lower()
    return Counter({
        _model_class_to_label(model_class): count
        for model_class, count in counter.items()
    })
