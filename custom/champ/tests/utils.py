import json
from django.test.testcases import TestCase
from django.test.client import RequestFactory
from django.test.testcases import SimpleTestCase
from fakecouch import FakeCouchDb

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.users.models import WebUser

from corehq.apps.domain.models import Domain
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.specs import FactoryContext
from corehq.apps.users.models import CommCareUser
import os


class ChampTestCase(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        # gets created + removed in package level setup / teardown
        domain = Domain.get_or_create_with_name('champ-cameroon')
        domain.is_active = True
        domain.save()
        cls.domain = domain
        cls.setup_subscription(cls.domain.name, SoftwarePlanEdition.ADVANCED)
        cls.user = WebUser.create(domain.name, 'test', 'passwordtest', None, None)
        cls.user.is_authenticated = True
        cls.user.is_superuser = True
        cls.user.is_authenticated = True
        cls.user.is_active = True

    @classmethod
    def tearDownClass(cls):
        cls.teardown_subscriptions()
        cls.user.delete(cls.domain.name, deleted_by=None)
        clear_plan_version_cache()
        super().tearDownClass()

    @classmethod
    def add_request_attrs(cls, request):
        request.user = cls.user
        request.domain = cls.domain.name


class TestDataSourceExpressions(SimpleTestCase):

    data_source_name = None

    def get_expression(self, column_id, column_type):
        column = self.get_column(column_id)
        if column['type'] == 'boolean':
            return FilterFactory.from_spec(
                column['filter'],
                FactoryContext(self.named_expressions, {})
            )
        else:
            self.assertEqual(column['datatype'], column_type)
            return ExpressionFactory.from_spec(
                column['expression'],
                FactoryContext(self.named_expressions, {})
            )

    @classmethod
    def setUpClass(cls):
        super(TestDataSourceExpressions, cls).setUpClass()

        data_source_file = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
            'ucr_data_sources',
            cls.data_source_name
        )

        with open(data_source_file, encoding='utf-8') as f:
            cls.data_source = DataSourceConfiguration.wrap(json.loads(f.read())['config'])
            cls.named_expressions = cls.data_source.named_expression_objects

    def setUp(self):
        self.database = FakeCouchDb()
        self.user_orig_db = CommCareUser.get_db()
        CommCareUser.set_db(self.database)

    def tearDown(self):
        CommCareUser.set_db(self.user_orig_db)

    def get_column(self, column_id):
        return [
            ind
            for ind in self.data_source.configured_indicators
            if ind['column_id'] == column_id
        ][0]
