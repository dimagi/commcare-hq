import json
import os
from contextlib import ExitStack
from unittest import mock

from django.test.client import RequestFactory
from django.test.testcases import SimpleTestCase, TestCase

import postgres_copy
import sqlalchemy
from fakecouch import FakeCouchDb
from unmagic import fixture

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    StaticDataSourceConfiguration,
)
from corehq.apps.userreports.specs import FactoryContext
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.sql_db.connections import UCR_ENGINE_ID, connection_manager


@fixture(scope="package")
def create_domain_with_ucr_fixtures():
    # ucr_fixtures will be setup for the first test that uses it (a
    # subclass of ChampTestCase) and torn down after all tests in the
    # "champ.tests" package have been run.

    def with_db(func):
        with db_blocker.unblock():
            func()

    db_blocker = fixture("django_db_blocker")()
    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )
    with _call_center_domain_mock, ExitStack() as on_exit:
        domain = create_domain('champ-cameroon')
        on_exit.callback(with_db, domain.delete)

        configs = StaticDataSourceConfiguration.by_domain(domain.name)
        adapters = [get_indicator_adapter(config) for config in configs]
        for adapter in adapters:
            adapter.build_table()
            on_exit.callback(with_db, adapter.drop_table)

        engine = connection_manager.get_engine(UCR_ENGINE_ID)
        metadata = sqlalchemy.MetaData(bind=engine)
        metadata.reflect(bind=engine, extend_existing=True)
        path = os.path.join(os.path.dirname(__file__), 'fixtures')
        for file_name in os.listdir(path):
            with open(os.path.join(path, file_name), encoding='utf-8') as f:
                table_name = get_table_name(domain.name, file_name[:-4])
                table = metadata.tables[table_name]
                postgres_copy.copy_from(f, table, engine, format='csv', null='', header=True)

        yield domain


class ChampTestCase(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        domain = create_domain_with_ucr_fixtures()
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
