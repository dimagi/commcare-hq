import inspect
import json
import uuid
from StringIO import StringIO
import functools
from collections import Counter

from django.db.models.signals import post_save
from django.test import TestCase
from django.test.utils import override_settings

from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.apps.commtrack.helpers import make_product
from corehq.apps.commtrack.tests.util import get_single_balance_block
from corehq.apps.domain.models import Domain
from corehq.apps.dump_reload.sql import dump_sql_data
from corehq.apps.dump_reload.sql import load_sql_data
from corehq.apps.dump_reload.sql.dump import get_model_domain_filters, get_objects_to_dump
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.form_processor.models import (
    XFormInstanceSQL, XFormAttachmentSQL, XFormOperationSQL,
    CommCareCaseSQL, CommCareCaseIndexSQL, CaseTransaction,
    LedgerValue, LedgerTransaction)
from corehq.form_processor.tests.utils import FormProcessorTestUtils, create_form_for_test
from django.core import serializers


def register_cleanup(test, models, domain):
    test.addCleanup(functools.partial(delete_sql_data, test, models, domain))


@override_settings(ALLOW_FORM_PROCESSING_QUERIES=True)
def delete_sql_data(test, models, domain):
    for model in models:
        filters = get_model_domain_filters(model, domain)
        for filter in filters:
            model.objects.filter(filter).delete()
            test.assertFalse(model.objects.filter(filter).exists(), model)


class BaseDumpLoadTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(BaseDumpLoadTest, cls).setUpClass()
        cls.domain = uuid.uuid4().hex

    @override_settings(ALLOW_FORM_PROCESSING_QUERIES=True)
    def _dump_and_load(self, expected_object_count, models):
        output_stream = StringIO()
        dump_sql_data(self.domain, [], output_stream)

        delete_sql_data(self, models, self.domain)

        # make sure that there's no data left in the DB
        objects_remaining = list(get_objects_to_dump(self.domain, []))
        object_classes = [obj.__class__.__name__ for obj in objects_remaining]
        counts = Counter(object_classes)
        self.assertEqual([], objects_remaining, 'Not all data deleted: {}'.format(counts))

        dump_output = output_stream.getvalue()
        dump_lines = [line.strip() for line in dump_output.split('\n') if line.strip()]
        total_object_count, loaded_object_count = load_sql_data(dump_lines)

        model_counts = Counter([json.loads(line)['model'] for line in dump_lines])
        msg = "{} != {}\n{}".format(expected_object_count, len(dump_lines), model_counts)
        self.assertEqual(expected_object_count, len(dump_lines), msg)
        self.assertEqual(expected_object_count, loaded_object_count)
        self.assertEqual(expected_object_count, total_object_count)

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
        cls.factory = CaseFactory(domain=cls.domain)
        cls.form_accessors = FormAccessors(cls.domain)
        cls.case_accessors = CaseAccessors(cls.domain)
        cls.product = make_product(cls.domain, 'A Product', 'prodcode_a')

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain)
        super(TestSQLDumpLoadShardedModels, cls).tearDownClass()

    def test_dump_laod_form(self):
        models_under_test = [XFormInstanceSQL, XFormAttachmentSQL, XFormOperationSQL]
        register_cleanup(self, models_under_test, self.domain)

        pre_forms = [
            create_form_for_test(self.domain),
            create_form_for_test(self.domain)
        ]
        expected_object_count = 4  # 2 forms, 2 form attachments
        self._dump_and_load(expected_object_count, models_under_test)

        form_ids = self.form_accessors.get_all_form_ids_in_domain('XFormInstance')
        self.assertEqual(set(form_ids), set(form.form_id for form in pre_forms))

        for pre_form in pre_forms:
            post_form = self.form_accessors.get_form(pre_form.form_id)
            self.assertDictEqual(pre_form.to_json(), post_form.to_json())

    def test_sql_dump_load_case(self):
        models_under_test = [
            XFormInstanceSQL, XFormAttachmentSQL, XFormOperationSQL,
            CommCareCaseSQL, CommCareCaseIndexSQL, CaseTransaction
        ]
        register_cleanup(self, models_under_test, self.domain)

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

        object_count = 10  # 2 forms, 2 form attachment, 2 cases, 3 case transactions, 1 case index
        self._dump_and_load(object_count, models_under_test)

        case_ids = self.case_accessors.get_case_ids_in_domain()
        self.assertEqual(set(case_ids), set(case.case_id for case in pre_cases))
        for pre_case in pre_cases:
            post_case = self.case_accessors.get_case(pre_case.case_id)
            self.assertDictEqual(pre_case.to_json(), post_case.to_json())

    def test_ledgers(self):
        models_under_test = [
            XFormInstanceSQL, XFormAttachmentSQL, XFormOperationSQL,
            CommCareCaseSQL, CommCareCaseIndexSQL, CaseTransaction,
            LedgerValue, LedgerTransaction
        ]
        register_cleanup(self, models_under_test, self.domain)

        case = self.factory.create_case()
        submit_case_blocks([
            get_single_balance_block(case.case_id, self.product._id, 10)
        ], self.domain)
        submit_case_blocks([
            get_single_balance_block(case.case_id, self.product._id, 5)
        ], self.domain)

        pre_ledger_values = LedgerAccessorSQL.get_ledger_values_for_case(case.case_id)
        pre_ledger_transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(case.case_id)
        self.assertEqual(1, len(pre_ledger_values))
        self.assertEqual(2, len(pre_ledger_transactions))

        # 3 forms, 3 form attachments, 1 case, 3 case transactions, 1 ledger value, 2 ledger transactions
        expected_doc_count = 13
        self._dump_and_load(expected_doc_count, models_under_test)

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
        models_under_test = [CaseSearchConfig]
        register_cleanup(self, models_under_test, self.domain)

        pre_config, created = CaseSearchConfig.objects.get_or_create(pk=self.domain)
        pre_config.enabled = True
        fuzzies = CaseSearchConfigJSON()
        fuzzies.add_fuzzy_properties('dog', ['breed', 'color'])
        fuzzies.add_fuzzy_properties('owner', ['name'])
        pre_config.config = fuzzies
        pre_config.save()

        self._dump_and_load(1, models_under_test)

        post_config = CaseSearchConfig.objects.get(domain=self.domain)
        self.assertTrue(post_config.enabled)
        self.assertDictEqual(pre_config.config.to_json(), post_config.config.to_json())

    def test_auto_case_update_rules(self):
        from corehq.apps.data_interfaces.models import (
            AutomaticUpdateRule, AutomaticUpdateRuleCriteria, AutomaticUpdateAction
        )
        models_under_test = [AutomaticUpdateAction, AutomaticUpdateRuleCriteria, AutomaticUpdateRule]
        register_cleanup(self, models_under_test, self.domain)

        pre_rule = AutomaticUpdateRule(
            domain=self.domain,
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

        self._dump_and_load(4, models_under_test)

        post_rule = AutomaticUpdateRule.objects.get(pk=pre_rule.pk)
        post_criteria = AutomaticUpdateRuleCriteria.objects.get(pk=pre_criteria.pk)
        post_action_update = AutomaticUpdateAction.objects.get(pk=pre_action_update.pk)
        post_action_close = AutomaticUpdateAction.objects.get(pk=pre_action_close.pk)

        self.assertModelsEqual(
            [pre_rule, pre_criteria, pre_action_update, pre_action_close],
            [post_rule, post_criteria, post_action_update, post_action_close]
        )

    @override_settings(AUDIT_MODEL_SAVE=[])
    def test_users(self):
        from corehq.apps.users.models import CommCareUser
        from corehq.apps.users.models import WebUser
        from django.contrib.auth.models import User
        from corehq.apps.tzmigration.models import TimezoneMigrationProgress

        models_under_test = [User, TimezoneMigrationProgress]
        register_cleanup(self, models_under_test, self.domain)

        ccdomain = Domain(name=self.domain)
        ccdomain.save()
        self.addCleanup(ccdomain.delete)

        ccuser_1 = CommCareUser.create(
            domain=self.domain,
            username='user_1',
            password='secret',
            email='email@example.com',
        )
        ccuser_2 = CommCareUser.create(
            domain=self.domain,
            username='user_2',
            password='secret',
            email='email1@example.com',
        )
        web_user = WebUser.create(
            domain=self.domain,
            username='webuser_1',
            password='secret',
            email='webuser@example.com',
        )
        self.addCleanup(ccuser_1.delete)
        self.addCleanup(ccuser_2.delete)
        self.addCleanup(web_user.delete)

        expected_object_count = 4  # 3 users, 1 time zone migration
        self._dump_and_load(expected_object_count, models_under_test)

    def test_device_logs(self):
        from corehq.apps.receiverwrapper.util import submit_form_locally
        from phonelog.models import DeviceReportEntry, ForceCloseEntry, UserEntry, UserErrorEntry
        from corehq.apps.users.models import CommCareUser
        from django.contrib.auth.models import User
        from corehq.apps.tzmigration.models import TimezoneMigrationProgress

        expected_models = [
            DeviceReportEntry, ForceCloseEntry, UserEntry, UserErrorEntry, User, TimezoneMigrationProgress
        ]
        register_cleanup(self, expected_models, self.domain)

        domain = Domain(name=self.domain)
        domain.save()
        self.addCleanup(domain.delete)

        user = CommCareUser.create(
            domain=self.domain,
            username='user_1',
            password='secret',
            email='email@example.com',
            uuid='428d454aa9abc74e1964e16d3565d6b6'  # match ID in devicelog.xml
        )
        self.addCleanup(user.delete)

        with open('corehq/ex-submodules/couchforms/tests/data/devicelogs/devicelog.xml') as f:
            xml = f.read()
        submit_form_locally(xml, self.domain)

        # 1 user, 7 device reports, 1 user entry, 2 user errors, 1 force close, 1 timezone migration
        expected_object_count = 13
        self._dump_and_load(expected_object_count, expected_models)

    def test_demo_user_restore(self):
        from corehq.apps.users.models import CommCareUser
        from corehq.apps.ota.models import DemoUserRestore
        from django.contrib.auth.models import User
        from corehq.apps.tzmigration.models import TimezoneMigrationProgress

        expected_models = [DemoUserRestore, User, TimezoneMigrationProgress]
        register_cleanup(self, expected_models, self.domain)

        domain = Domain(name=self.domain)
        domain.save()
        self.addCleanup(domain.delete)

        user_id = uuid.uuid4().hex
        user = CommCareUser.create(
            domain=self.domain,
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

        expected_object_count = 3  # 1 user, 1 demo ser restore, 1 timezone migration
        self._dump_and_load(expected_object_count, expected_models)

    def test_timezone_migration_progress(self):
        from corehq.apps.tzmigration.models import TimezoneMigrationProgress

        expected_models = [TimezoneMigrationProgress]
        register_cleanup(self, expected_models, self.domain)

        TimezoneMigrationProgress(domain=self.domain).save()

        self._dump_and_load(1, expected_models)
