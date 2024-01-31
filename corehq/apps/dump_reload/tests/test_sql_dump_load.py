import inspect
import json
import uuid
from collections import Counter
from datetime import datetime
from io import StringIO
from pathlib import Path

from unittest import mock
from django.contrib.admin.utils import NestedObjects
from django.db import transaction, IntegrityError
from django.db.models.signals import post_delete, post_save
from django.test import SimpleTestCase, TestCase
from nose.tools import nottest

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.commtrack.helpers import make_product
from corehq.apps.commtrack.tests.util import get_single_balance_block
from corehq.apps.domain.models import Domain
from corehq.apps.dump_reload.sql import SqlDataDumper, SqlDataLoader
from corehq.apps.dump_reload.sql.dump import (
    get_model_iterator_builders_to_dump,
    get_objects_to_dump,
)
from corehq.apps.dump_reload.sql.load import (
    DefaultDictWithKey,
    constraint_checks_deferred,
    update_model_name,
)
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.products.models import SQLProduct
from corehq.apps.zapier.consts import EventTypes
from corehq.apps.zapier.models import ZapierSubscription
from corehq.apps.zapier.signals.receivers import (
    zapier_subscription_post_delete,
)
from corehq.blobs.models import BlobMeta
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.models import (
    CaseTransaction,
    CommCareCaseIndex,
    CommCareCase,
    LedgerTransaction,
    LedgerValue,
    XFormInstance,
)
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    create_form_for_test,
    sharded,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    AlertScheduleInstance,
)
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import CreateCaseRepeater


class BaseDumpLoadTest(TestCase):
    @classmethod
    def setUpClass(cls):
        post_delete.disconnect(zapier_subscription_post_delete, sender=ZapierSubscription)
        super(BaseDumpLoadTest, cls).setUpClass()
        cls.domain_name = uuid.uuid4().hex
        cls.domain = Domain(name=cls.domain_name)
        cls.domain.save()

        cls.default_objects_counts = Counter({})

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(BaseDumpLoadTest, cls).tearDownClass()
        post_delete.connect(zapier_subscription_post_delete, sender=ZapierSubscription)

    def delete_sql_data(self):
        delete_domain_sql_data_for_dump_load_test(self.domain_name)

    def tearDown(self):
        self.delete_sql_data()
        super(BaseDumpLoadTest, self).tearDown()

    def _dump_and_load(self, expected_dump_counts, load_filter=None, expected_load_counts=None):
        expected_load_counts = expected_load_counts or expected_dump_counts
        expected_dump_counts.update(self.default_objects_counts)

        models = list(expected_dump_counts)
        self._check_signals_handle_raw(models)

        # Dump
        dumper = SqlDataDumper(self.domain_name, [], [])
        dumper.stdout = None  # silence output
        output_stream = StringIO()
        dumper.dump(output_stream)
        output_stream.seek(0)

        self.delete_sql_data()
        self._do_load(output_stream, expected_dump_counts, load_filter, expected_load_counts)

    def _load(self, output_stream, expected_load_counts):
        expected_load_counts.update(self.default_objects_counts)
        self._do_load(output_stream, expected_load_counts, None, expected_load_counts)

    def _do_load(self, output_stream, expected_dump_counts, load_filter, expected_load_counts):
        # make sure that there's no data left in the DB
        objects_remaining = list(get_objects_to_dump(self.domain_name, [], []))
        object_classes = [obj.__class__.__name__ for obj in objects_remaining]
        counts = Counter(object_classes)
        self.assertEqual([], objects_remaining, 'Not all data deleted: {}'.format(counts))

        actual_model_counts, dump_lines = self._parse_dump_output(output_stream)
        expected_model_counts = _normalize_object_counter(expected_dump_counts)
        self.assertDictEqual(dict(expected_model_counts), dict(actual_model_counts))

        # Load
        loader = SqlDataLoader(object_filter=load_filter)
        loaded_model_counts = loader.load_objects(dump_lines)

        normalized_expected_loaded_counts = _normalize_object_counter(expected_load_counts, for_loaded=True)
        self.assertDictEqual(dict(normalized_expected_loaded_counts), dict(loaded_model_counts))
        self.assertEqual(sum(expected_load_counts.values()), sum(loaded_model_counts.values()))

        return dump_lines

    def _parse_dump_output(self, output_stream):
        def get_model(line):
            obj = json.loads(line)
            update_model_name(obj)
            return obj["model"]

        dump_output = output_stream.readlines()
        dump_lines = [line.strip() for line in dump_output if line.strip()]
        actual_model_counts = Counter([get_model(line) for line in dump_lines])
        return actual_model_counts, dump_lines

    def _check_signals_handle_raw(self, models):
        """Ensure that any post_save signal handlers have been updated
        to handle 'raw' calls."""
        whitelist_receivers = [
            'django_digest.models._post_save_persist_partial_digests'
        ]
        for model in models:
            for receiver in post_save._live_receivers(model):
                receiver_path = receiver.__module__ + '.' + receiver.__name__
                if receiver_path in whitelist_receivers:
                    continue
                args = inspect.signature(receiver).parameters
                message = 'Signal handler "{}" for model "{}" missing raw arg'.format(
                    receiver, model
                )
                self.assertIn('raw', args, message)


@nottest
def delete_domain_sql_data_for_dump_load_test(domain_name):
    for model_class, builder in get_model_iterator_builders_to_dump(domain_name, [], []):
        for iterator in builder.querysets():
            with transaction.atomic(using=iterator.db), \
                 constraint_checks_deferred(iterator.db):
                collector = NestedObjects(using=iterator.db)
                collector.collect(iterator)
                collector.delete()

    assert [] == list(get_objects_to_dump(domain_name, [], [])), "Not all SQL objects deleted"


@sharded
class TestSQLDumpLoadShardedModels(BaseDumpLoadTest):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(TestSQLDumpLoadShardedModels, cls).setUpClass()
        cls.factory = CaseFactory(domain=cls.domain_name)
        cls.product = make_product(cls.domain_name, 'A Product', 'prodcode_a')
        cls.default_objects_counts.update({SQLProduct: 1})

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain_name)
        super(TestSQLDumpLoadShardedModels, cls).tearDownClass()

    def test_dump_load_form(self):
        expected_object_counts = Counter({
            XFormInstance: 2,
            BlobMeta: 2
        })

        pre_forms = [
            create_form_for_test(self.domain_name),
            create_form_for_test(self.domain_name)
        ]
        self._dump_and_load(expected_object_counts)

        form_ids = XFormInstance.objects.get_form_ids_in_domain(self.domain_name, 'XFormInstance')
        self.assertEqual(set(form_ids), set(form.form_id for form in pre_forms))

        for pre_form in pre_forms:
            post_form = XFormInstance.objects.get_form(pre_form.form_id)
            self.assertDictEqual(pre_form.to_json(), post_form.to_json())

    def test_load_renamed_model(self):
        self.delete_sql_data()  # delete "default objects" created in setUpClass
        expected_object_counts = Counter({
            BlobMeta: 2,
            CommCareCase: 2,
            CommCareCaseIndex: 1,
            CaseTransaction: 3,
            XFormInstance: 2,
        })

        path = Path(__file__).parent / 'data/old-model-names.json'
        with open(path, encoding="utf8") as stream:
            self._load(stream, expected_object_counts)

        domain = "d47de5734d2c4670a8c294b51788075f"
        form_ids = XFormInstance.objects.get_form_ids_in_domain(domain, 'XFormInstance')
        self.assertEqual(set(form_ids), {
            '580987967edf45169574193f844e97dc',
            '56e8ba18e6ab407c862309f421930a7c',
        })
        case_ids = CommCareCase.objects.get_case_ids_in_domain(domain)
        self.assertEqual(set(case_ids), {
            '1ff125c3ad39412891a7be47a590cd5d',
            'f9e768d36ca34a5a95dca40a75488863',
        })

    def test_sql_dump_load_case(self):
        expected_object_counts = Counter({
            XFormInstance: 2,
            BlobMeta: 2,
            CommCareCase: 2,
            CaseTransaction: 3,
            CommCareCaseIndex: 1

        })

        pre_cases = self.factory.create_or_update_case(
            CaseStructure(
                attrs={'case_name': 'child', 'update': {'age': 3, 'diabetic': False}, 'create': True},
                indices=[
                    CaseIndex(CaseStructure(attrs={'case_name': 'parent', 'update': {'age': 42}, 'create': True})),
                ]
            )
        )
        pre_cases[0] = self.factory.create_or_update_case(CaseStructure(
            case_id=pre_cases[0].case_id,
            attrs={'external_id': 'billie jean', 'update': {'name': 'Billie Jean'}}
        ))[0]

        self._dump_and_load(expected_object_counts)

        case_ids = CommCareCase.objects.get_case_ids_in_domain(self.domain_name)
        self.assertEqual(set(case_ids), set(case.case_id for case in pre_cases))
        for pre_case in pre_cases:
            post_case = CommCareCase.objects.get_case(pre_case.case_id, self.domain_name)
            self.assertDictEqual(pre_case.to_json(), post_case.to_json())

    def test_ledgers(self):
        expected_object_counts = Counter({
            XFormInstance: 3,
            BlobMeta: 3,
            CommCareCase: 1,
            CaseTransaction: 3,
            LedgerValue: 1,
            LedgerTransaction: 2

        })

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
    def test_case_search_config(self):
        from corehq.apps.case_search.models import CaseSearchConfig, FuzzyProperties
        expected_object_counts = Counter({
            CaseSearchConfig: 1,
            FuzzyProperties: 2,
        })

        pre_config, created = CaseSearchConfig.objects.get_or_create(pk=self.domain_name)
        pre_config.enabled = True
        pre_fuzzies = [
            FuzzyProperties(domain=self.domain, case_type='dog', properties=['breed', 'color']),
            FuzzyProperties(domain=self.domain, case_type='owner', properties=['name']),
        ]
        for fuzzy in pre_fuzzies:
            fuzzy.save()
        pre_config.fuzzy_properties.set(pre_fuzzies)
        pre_config.save()

        self._dump_and_load(expected_object_counts)

        post_config = CaseSearchConfig.objects.get(domain=self.domain_name)
        self.assertTrue(post_config.enabled)
        self.assertEqual(pre_config.fuzzy_properties, post_config.fuzzy_properties)
        post_fuzzies = FuzzyProperties.objects.filter(domain=self.domain_name)
        self.assertEqual(set(f.case_type for f in post_fuzzies), {'dog', 'owner'})

    def test_users(self):
        from corehq.apps.users.models import CommCareUser
        from corehq.apps.users.models import WebUser
        from django.contrib.auth.models import User

        expected_object_counts = Counter({User: 3})

        ccuser_1 = CommCareUser.create(
            domain=self.domain_name,
            username='user_1',
            password='secret',
            created_by=None,
            created_via=None,
            email='email@example.com',
        )
        ccuser_2 = CommCareUser.create(
            domain=self.domain_name,
            username='user_2',
            password='secret',
            created_by=None,
            created_via=None,
            email='email1@example.com',
        )
        web_user = WebUser.create(
            domain=self.domain_name,
            username='webuser_t1',
            password='secret',
            created_by=None,
            created_via=None,
            email='webuser@example.com',
        )
        self.addCleanup(ccuser_1.delete, self.domain_name, deleted_by=None)
        self.addCleanup(ccuser_2.delete, self.domain_name, deleted_by=None)
        self.addCleanup(web_user.delete, self.domain_name, deleted_by=None)

        self._dump_and_load(expected_object_counts)

    def test_sqluserdata(self):
        from corehq.apps.users.models import SQLUserData, WebUser
        from django.contrib.auth.models import User

        expected_object_counts = Counter({User: 1, SQLUserData: 1})

        web_user = WebUser.create(
            domain=self.domain_name,
            username='webuser_t1',
            password='secret',
            created_by=None,
            created_via=None,
            email='webuser@example.com',
        )
        self.addCleanup(web_user.delete, self.domain_name, deleted_by=None)
        user = web_user.get_django_user()
        SQLUserData.objects.create(domain=self.domain_name, data={'test': 1}, django_user=user)

        self._dump_and_load(expected_object_counts)

    def test_dump_roles(self):
        from corehq.apps.users.models import UserRole, HqPermissions, RoleAssignableBy, RolePermission

        expected_object_counts = Counter({
            UserRole: 2,
            RolePermission: 5,
            RoleAssignableBy: 1
        })

        role1 = UserRole.create(self.domain_name, 'role1')
        role2 = UserRole.create(
            self.domain_name, 'role1',
            permissions=HqPermissions(edit_web_users=True),
            assignable_by=[role1.id]
        )
        self.addCleanup(role1.delete)
        self.addCleanup(role2.delete)

        self._dump_and_load(expected_object_counts)

        role1_loaded = UserRole.objects.get(id=role1.id)
        role2_loaded = UserRole.objects.get(id=role2.id)

        self.assertEqual(role1_loaded.permissions.to_list(), HqPermissions().to_list())
        self.assertEqual(role1_loaded.assignable_by, [])
        self.assertEqual(role2_loaded.permissions.to_list(), HqPermissions(edit_web_users=True).to_list())
        self.assertEqual(role2_loaded.assignable_by, [role1_loaded.get_id])

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

        user = CommCareUser.create(
            domain=self.domain_name,
            username='user_1',
            password='secret',
            created_by=None,
            created_via=None,
            email='email@example.com',
            uuid='428d454aa9abc74e1964e16d3565d6b6'  # match ID in devicelog.xml
        )
        self.addCleanup(user.delete, self.domain_name, deleted_by=None)

        with open('corehq/ex-submodules/couchforms/tests/data/devicelogs/devicelog.xml', 'rb') as f:
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

        user_id = uuid.uuid4().hex
        user = CommCareUser.create(
            domain=self.domain_name,
            username='user_1',
            password='secret',
            created_by=None,
            created_via=None,
            email='email@example.com',
            uuid=user_id
        )
        self.addCleanup(user.delete, self.domain_name, deleted_by=None)

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

        p1 = SQLProduct.objects.create(domain=self.domain_name, product_id='test1', name='test1')
        p2 = SQLProduct.objects.create(domain=self.domain_name, product_id='test2', name='test2')
        parchived = SQLProduct.objects.create(
            domain=self.domain_name, product_id='test3', name='test3', is_archived=True)

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

    def test_sms(self):
        from corehq.apps.sms.models import PhoneNumber, MessagingEvent, MessagingSubEvent
        expected_object_counts = Counter({PhoneNumber: 1, MessagingEvent: 1, MessagingSubEvent: 1})

        phone_number = PhoneNumber(
            domain=self.domain_name,
            owner_doc_type='CommCareCase',
            owner_id='fake-owner-id1',
            phone_number='99912341234',
            backend_id=None,
            ivr_backend_id=None,
            verified=True,
            is_two_way=True,
            pending_verification=False,
            contact_last_modified=datetime.utcnow()
        )
        phone_number.save()
        event = MessagingEvent.objects.create(
            domain=self.domain_name,
            date=datetime.utcnow(),
            source=MessagingEvent.SOURCE_REMINDER,
            content_type=MessagingEvent.CONTENT_SMS,
            status=MessagingEvent.STATUS_COMPLETED
        )
        MessagingSubEvent.objects.create(
            parent=event,
            domain=self.domain_name,
            date=datetime.utcnow(),
            recipient_type=MessagingEvent.RECIPIENT_CASE,
            content_type=MessagingEvent.CONTENT_SMS,
            status=MessagingEvent.STATUS_COMPLETED
        )

        self._dump_and_load(expected_object_counts)

    def test_message_scheduling(self):
        AlertScheduleInstance(
            schedule_instance_id=uuid.uuid4(),
            domain=self.domain_name,
            recipient_type='CommCareUser',
            recipient_id=uuid.uuid4().hex,
            current_event_num=0,
            schedule_iteration_num=1,
            next_event_due=datetime(2017, 3, 1),
            active=True,
            alert_schedule_id=uuid.uuid4(),
        ).save()
        self._dump_and_load({AlertScheduleInstance: 1})

    def test_mobile_backend(self):
        from corehq.apps.sms.models import (
            SQLMobileBackend,
            SQLMobileBackendMapping,
        )

        domain_backend = SQLMobileBackend.objects.create(
            domain=self.domain_name,
            name='test-domain-mobile-backend',
            display_name='Test Domain Mobile Backend',
            hq_api_id='TDMB',
            inbound_api_key='test-domain-mobile-backend-inbound-api-key',
            supported_countries=["*"],
            backend_type=SQLMobileBackend.SMS,
            is_global=False,
        )
        SQLMobileBackendMapping.objects.create(
            domain=self.domain_name,
            backend=domain_backend,
            backend_type=SQLMobileBackend.SMS,
            prefix='123',
        )

        global_backend = SQLMobileBackend.objects.create(
            domain=None,
            name='test-global-mobile-backend',
            display_name='Test Global Mobile Backend',
            hq_api_id='TGMB',
            inbound_api_key='test-global-mobile-backend-inbound-api-key',
            supported_countries=["*"],
            backend_type=SQLMobileBackend.SMS,
            is_global=True,
        )
        SQLMobileBackendMapping.objects.create(
            domain=self.domain_name,
            backend=global_backend,
            backend_type=SQLMobileBackend.SMS,
            prefix='*',
        )
        self._dump_and_load({
            SQLMobileBackendMapping: 1,
            SQLMobileBackend: 1,
        })
        self.assertEqual(SQLMobileBackend.objects.first().domain,
                         self.domain_name)
        self.assertEqual(SQLMobileBackendMapping.objects.first().domain,
                         self.domain_name)

    def test_case_importer(self):
        from corehq.apps.case_importer.tracking.models import (
            CaseUploadFileMeta,
            CaseUploadFormRecord,
            CaseUploadRecord,
        )

        upload_file_meta = CaseUploadFileMeta.objects.create(
            identifier=uuid.uuid4().hex,
            filename='picture.jpg',
            length=1024,
        )
        case_upload_record = CaseUploadRecord.objects.create(
            domain=self.domain_name,
            upload_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            couch_user_id=uuid.uuid4().hex,
            case_type='person',
            upload_file_meta=upload_file_meta,
        )
        CaseUploadFormRecord.objects.create(
            case_upload_record=case_upload_record,
            form_id=uuid.uuid4().hex,
        )
        self._dump_and_load(Counter({
            CaseUploadFileMeta: 1,
            CaseUploadRecord: 1,
            CaseUploadFormRecord: 1,
        }))

    def test_transifex(self):
        from corehq.apps.translations.models import TransifexProject, TransifexOrganization
        org = TransifexOrganization.objects.create(slug='test', name='demo', api_token='123')
        TransifexProject.objects.create(
            organization=org, slug='testp', name='demop', domain=self.domain_name
        )
        TransifexProject.objects.create(
            organization=org, slug='testp1', name='demop1', domain=self.domain_name
        )
        self._dump_and_load(Counter({TransifexOrganization: 1, TransifexProject: 2}))

    def test_filtered_dump_load(self):
        from corehq.apps.locations.tests.test_location_types import make_loc_type
        from corehq.apps.products.models import SQLProduct
        from corehq.apps.locations.models import LocationType

        make_loc_type('state', domain=self.domain_name)
        SQLProduct.objects.create(domain=self.domain_name, product_id='test1', name='test1')
        expected_object_counts = Counter({LocationType: 1, SQLProduct: 1})

        self._dump_and_load(expected_object_counts, load_filter='sqlproduct',
            expected_load_counts=Counter({SQLProduct: 1}))
        self.assertEqual(0, LocationType.objects.count())

    def test_sms_content(self):
        from corehq.messaging.scheduling.models import AlertSchedule, SMSContent, AlertEvent
        from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import \
            delete_alert_schedule_instances_for_schedule

        schedule = AlertSchedule.create_simple_alert(self.domain, SMSContent())

        schedule.set_custom_alert(
            [
                (AlertEvent(minutes_to_wait=5), SMSContent()),
                (AlertEvent(minutes_to_wait=15), SMSContent()),
            ]
        )

        self.addCleanup(lambda: delete_alert_schedule_instances_for_schedule(
            AlertScheduleInstance, schedule.schedule_id))
        self._dump_and_load(Counter({AlertSchedule: 1, AlertEvent: 2, SMSContent: 2}))

    def test_zapier_subscription(self):
        ZapierSubscription.objects.create(
            domain=self.domain_name,
            case_type='case_type',
            event_name=EventTypes.NEW_CASE,
            url='example.com',
            user_id='user_id',
        )
        self._dump_and_load(Counter({CreateCaseRepeater: 1, ConnectionSettings: 1, ZapierSubscription: 1}))

    def test_lookup_table(self):
        from corehq.apps.fixtures.models import (
            Field,
            LookupTable,
            LookupTableRow,
            LookupTableRowOwner,
            OwnerType,
            TypeField,
        )
        table = LookupTable.objects.create(
            domain=self.domain_name,
            tag="dump-load",
            fields=[
                TypeField("country", is_indexed=True),
                TypeField("state_name", properties=["lang"]),
                TypeField("state_id"),
            ]
        )
        row = LookupTableRow.objects.create(
            domain=self.domain_name,
            table_id=table.id,
            fields={
                "country": [
                    Field("India"),
                ],
                "state_name": [
                    Field("Delhi_IN_ENG", properties={"lang": "eng"}),
                    Field("Delhi_IN_HIN", properties={"lang": "hin"}),
                ],
                "state_id": [
                    Field("DEL"),
                ],
            },
            sort_key=0,
        )
        LookupTableRowOwner.objects.create(
            domain=self.domain_name,
            row_id=row.id,
            owner_type=OwnerType.User,
            owner_id="abc",
        )
        self._dump_and_load(Counter({LookupTable: 1, LookupTableRow: 1, LookupTableRowOwner: 1}))


@mock.patch("corehq.apps.dump_reload.sql.load.ENQUEUE_TIMEOUT", 1)
class TestSqlLoadWithError(BaseDumpLoadTest):
    def setUp(self):
        self.products = [
            SQLProduct.objects.create(domain=self.domain_name, product_id='test1', name='test1'),
            SQLProduct.objects.create(domain=self.domain_name, product_id='test2', name='test2'),
            SQLProduct.objects.create(domain=self.domain_name, product_id='test3', name='test3'),
        ]

    def test_load_error_queue_full(self):
        """Blocks when sending 'test3'"""
        self._load_with_errors(chunk_size=1)

    def test_load_error_queue_full_on_terminate(self):
        """Blocks when sending ``None`` into the queue to 'terminate' it."""
        self._load_with_errors(chunk_size=2)

    def _load_with_errors(self, chunk_size):
        output_stream = StringIO()
        dumper = SqlDataDumper(self.domain_name, [], [])
        dumper.stdout = None
        dumper.dump(output_stream)
        output_stream.seek(0)
        self.delete_sql_data()
        # resave the product to force an error
        self.products[0].save()
        actual_model_counts, dump_lines = self._parse_dump_output(output_stream)
        self.assertEqual(actual_model_counts['products.sqlproduct'], 3)

        loader = SqlDataLoader()
        with self.assertRaises(IntegrityError), \
             mock.patch("corehq.apps.dump_reload.sql.load.CHUNK_SIZE", chunk_size):
            # patch the chunk size so that the queue blocks
            loader.load_objects(dump_lines)


class DefaultDictWithKeyTests(SimpleTestCase):

    def test_intended_use_case(self):
        def enlist(item):
            return [item]
        greasy_spoon = DefaultDictWithKey(enlist)
        self.assertEqual(greasy_spoon['spam'], ['spam'])
        greasy_spoon['spam'].append('spam')
        self.assertEqual(greasy_spoon['spam'], ['spam', 'spam'])

    def test_not_enough_params(self):
        def empty_list():
            return []
        greasy_spoon = DefaultDictWithKey(empty_list)
        with self.assertRaisesRegex(
            TypeError,
            r'empty_list\(\) takes 0 positional arguments but 1 was given'
        ):
            greasy_spoon['spam']

    def test_too_many_params(self):
        def appender(item1, item2):
            return [item1, item2]
        greasy_spoon = DefaultDictWithKey(appender)
        with self.assertRaisesRegex(
            TypeError,
            r"appender\(\) missing 1 required positional argument: 'item2'"
        ):
            greasy_spoon['spam']

    def test_no_factory(self):
        greasy_spoon = DefaultDictWithKey()
        with self.assertRaisesRegex(
            TypeError,
            "'NoneType' object is not callable"
        ):
            greasy_spoon['spam']


def _normalize_object_counter(counter, for_loaded=False):
    """Converts a <Model Class> keyed counter to an model label keyed counter"""
    def _model_class_to_label(model_class):
        label = '{}.{}'.format(model_class._meta.app_label, model_class.__name__)
        return label if for_loaded else label.lower()
    return Counter({
        _model_class_to_label(model_class): count
        for model_class, count in counter.items()
    })
