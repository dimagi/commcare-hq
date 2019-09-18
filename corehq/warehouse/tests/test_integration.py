from datetime import datetime

from casexml.apps.phone.models import OTARestoreCommCareUser
from casexml.apps.phone.utils import MockDevice
from corehq.apps.users.models import CommCareUser
from corehq.apps.domain.models import Domain
from corehq.dbaccessors.couchapps.all_docs import delete_all_docs_by_doc_type
from corehq.form_processor.tests.utils import create_form_for_test, FormProcessorTestUtils

from corehq.warehouse.tests.utils import create_batch, BaseWarehouseTestCase
from corehq.warehouse.models import (
    UserStagingTable,
    DomainStagingTable,
    UserDim,
    DomainDim,
    FormStagingTable,
    FormFact,
    Batch,
    SyncLogStagingTable,
    SyncLogFact,
    AppStatusFormStaging,
    AppStatusSynclogStaging,
    ApplicationStatusFact,
    get_cls_by_slug,
    ApplicationStagingTable,
    ApplicationDim
)


def teardown_module():
    Batch.objects.all().delete()


class AppStatusIntegrationTest(BaseWarehouseTestCase):
    domain = 'form-fact-integration-test'
    slug = 'form_fact'

    @classmethod
    def setUpClass(cls):
        super(AppStatusIntegrationTest, cls).setUpClass()
        delete_all_docs_by_doc_type(Domain.get_db(), ['Domain', 'Domain-Deleted'])
        delete_all_docs_by_doc_type(CommCareUser.get_db(), ['CommCareUser', 'WebUser'])
        cls.domain_records = [
            Domain(name=cls.domain, hr_name='One', creating_user_id='abc', is_active=True),
        ]

        for domain in cls.domain_records:
            domain.save()

        cls.user_records = [
            # TODO: Handle WebUsers who have multiple domains
            # WebUser.create(
            #     cls.domain,
            #     'web-user',
            #     '***',
            #     date_joined=datetime.utcnow(),
            #     first_name='A',
            #     last_name='B',
            #     email='b@a.com',
            #     is_active=True,
            #     is_staff=False,
            #     is_superuser=True,
            # ),
            CommCareUser.create(
                cls.domain,
                'commcare-user',
                '***',
                date_joined=datetime.utcnow(),
                email='a@a.com',
                is_active=True,
                is_staff=True,
                is_superuser=False,
            ),
        ]

        cls.form_records = [
            create_form_for_test(cls.domain, user_id=cls.user_records[0]._id),
            create_form_for_test(cls.domain, user_id=cls.user_records[0]._id),
            create_form_for_test(cls.domain, user_id=cls.user_records[0]._id),
        ]

        cls.sync_records = []
        for user in cls.user_records:
            restore_user = OTARestoreCommCareUser(user.domain, user)
            device = MockDevice(cls.domain_records[0], restore_user)
            cls.sync_records.append(device.sync())

        cls.batch = create_batch(cls.slug)

    @classmethod
    def tearDownClass(cls):
        for user in cls.user_records:
            user.delete()

        for domain in cls.domain_records:
            domain.delete()

        FormProcessorTestUtils.delete_all_sql_forms(cls.domain)

        FormStagingTable.clear_records()
        FormFact.clear_records()
        DomainStagingTable.clear_records()
        DomainDim.clear_records()
        UserStagingTable.clear_records()
        UserDim.clear_records()
        SyncLogStagingTable.clear_records()
        SyncLogFact.clear_records()
        AppStatusFormStaging.clear_records()
        AppStatusSynclogStaging.clear_records()
        ApplicationStatusFact.clear_records()
        super(AppStatusIntegrationTest, cls).tearDownClass()

    def test_loading_app_stats_fact(self):
        batch = self.batch

        seen = set()

        def commit_with_dependencies(clazz, path=None):
            path = path or []
            path.append(clazz)

            for dep in clazz.dependencies():
                dep_cls = get_cls_by_slug(dep)
                if dep_cls in path:
                    continue
                commit_with_dependencies(dep_cls, path)

            if clazz not in seen:
                seen.add(clazz)
                clazz.commit(batch)

        commit_with_dependencies(ApplicationStatusFact)

        expected_by_class = {
            ApplicationStagingTable: 0,
            ApplicationDim: 0,
            DomainStagingTable: len(self.domain_records),
            DomainDim: len(self.domain_records),
            UserStagingTable: len(self.user_records),
            UserDim: len(self.user_records),
            FormStagingTable: len(self.form_records),
            SyncLogStagingTable: len(self.user_records),
            AppStatusFormStaging: len(self.user_records),
            AppStatusSynclogStaging: len(self.user_records),
            ApplicationStatusFact: len(self.user_records),
        }
        for clazz in seen:
            expected = expected_by_class.pop(clazz)
            self.assertEqual(clazz.objects.count(), expected)

        self.assertFalse(expected_by_class, 'Not all classes checked')

        user = self.user_records[0]
        facts = ApplicationStatusFact.objects.filter(user_dim__user_id=user.user_id)
        self.assertEqual(len(facts), 1)
        app_status_fact = facts[0]
        self.assertEqual(app_status_fact.batch.id, batch.id)
        self.assertEqual(app_status_fact.domain, self.domain)
        self.assertEqual(app_status_fact.app_dim, None)
        self.assertEqual(app_status_fact.last_form_submission_date, self.form_records[-1].received_on)
        self.assertEqual(app_status_fact.last_sync_log_date, self.sync_records[-1].log.date)
        self.assertEqual(app_status_fact.last_form_app_build_version, None)
        self.assertEqual(app_status_fact.last_form_app_commcare_version, None)
