import json
from django.test.testcases import TestCase
from django.test.client import RequestFactory
from django.test.testcases import SimpleTestCase
from fakecouch import FakeCouchDb
from corehq.apps.users.models import WebUser

from corehq.apps.domain.models import Domain
from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.expressions import ExpressionFactory
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.specs import FactoryContext
from corehq.apps.users.models import CommCareUser
from couchforms.models import XFormInstance
import os


class YeksiTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('test-pna')
        domain.is_active = True
        domain.save()
        cls.domain = domain
        user = WebUser.get_by_username('test')
        if not user:
            user = WebUser.create(domain.name, 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        cls.user = user

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super().tearDownClass()


class TestDataSourceExpressions(SimpleTestCase):

    data_source_name = None

    def get_expression(self, column_id, column_type):
        column = self.get_column(column_id)
        if column['type'] == 'boolean':
            return FilterFactory.from_spec(
                column['filter'],
                context=FactoryContext(self.named_expressions, {})
            )
        else:
            self.assertEqual(column['datatype'], column_type)
            return ExpressionFactory.from_spec(
                column['expression'],
                context=FactoryContext(self.named_expressions, {})
            )

    def get_expressions_from_base_item_expression(self):
        return ExpressionFactory.from_spec(
            self.base_item_expression,
            context=FactoryContext(self.base_item_expression, {})
        )

    @classmethod
    def setUpClass(cls):
        super(TestDataSourceExpressions, cls).setUpClass()

        data_source_file = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
            'ucr',
            'data_sources',
            cls.data_source_name
        )

        with open(data_source_file, encoding='utf-8') as f:
            cls.data_source = DataSourceConfiguration.wrap(json.loads(f.read())['config'])
            cls.named_expressions = cls.data_source.named_expression_objects
            cls.base_item_expression = cls.data_source.base_item_expression

    def setUp(self):
        self.database = FakeCouchDb()
        self.case_orig_db = CommCareCase.get_db()
        self.form_orig_db = XFormInstance.get_db()
        self.user_orig_db = CommCareUser.get_db()
        CommCareCase.set_db(self.database)
        XFormInstance.set_db(self.database)
        CommCareUser.set_db(self.database)

    def tearDown(self):
        CommCareCase.set_db(self.case_orig_db)
        XFormInstance.set_db(self.form_orig_db)
        CommCareUser.set_db(self.user_orig_db)

    def get_column(self, column_id):
        for indicator in self.data_source.configured_indicators:
            if indicator['column_id'] == column_id:
                return indicator
