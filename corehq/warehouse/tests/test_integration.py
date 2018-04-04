from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, timedelta

from corehq.apps.users.models import CommCareUser
from corehq.apps.domain.models import Domain
from corehq.dbaccessors.couchapps.all_docs import delete_all_docs_by_doc_type
from corehq.form_processor.tests.utils import create_form_for_test, FormProcessorTestUtils

from corehq.warehouse.tests.utils import DEFAULT_BATCH_ID, create_batch, get_default_batch, BaseWarehouseTestCase
from corehq.warehouse.models import (
    UserStagingTable,
    DomainStagingTable,
    UserDim,
    DomainDim,
    FormStagingTable,
    FormFact,
    Batch,
)


def setup_module():
    start = datetime.utcnow() - timedelta(days=3)
    end = datetime.utcnow() + timedelta(days=3)
    create_batch(start, end, DEFAULT_BATCH_ID)


def teardown_module():
    Batch.objects.all().delete()


class FormFactIntegrationTest(BaseWarehouseTestCase):
    '''
    Tests a full integration of loading the FormFact table from
    staging and dimension tables.
    '''
    domain = 'form-fact-integration-test'

    @classmethod
    def setUpClass(cls):
        super(FormFactIntegrationTest, cls).setUpClass()
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
        super(FormFactIntegrationTest, cls).tearDownClass()

    def test_loading_form_fact(self):
        batch = get_default_batch()

        DomainStagingTable.commit(batch)
        self.assertEqual(DomainStagingTable.objects.count(), len(self.domain_records))

        DomainDim.commit(batch)
        self.assertEqual(DomainDim.objects.count(), len(self.domain_records))

        UserStagingTable.commit(batch)
        self.assertEqual(UserStagingTable.objects.count(), len(self.user_records))

        UserDim.commit(batch)
        self.assertEqual(UserDim.objects.count(), len(self.user_records))

        FormStagingTable.commit(batch)
        self.assertEqual(FormStagingTable.objects.count(), len(self.form_records))

        FormFact.commit(batch)
        self.assertEqual(FormFact.objects.count(), len(self.form_records))
