from __future__ import absolute_import

import json
import os

from django.test.testcases import SimpleTestCase
from fakecouch import FakeCouchDb

from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.expressions import ExpressionFactory
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.specs import FactoryContext


class TestDataSourceExpressions(SimpleTestCase):

    data_source_name = None

    def get_expression(self, column_id, column_type):
        column = self.get_column(column_id)
        self.assertEqual(column['datatype'], column_type)
        if column['type'] == 'boolean':
            return FilterFactory.from_spec(
                column['filter'],
                context=FactoryContext(self.named_expressions, {})
            )
        return ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

    @classmethod
    def setUpClass(cls):
        super(TestDataSourceExpressions, cls).setUpClass()

        data_source_file = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
            'data_sources',
            cls.data_source_name
        )

        with open(data_source_file) as f:
            cls.data_source = DataSourceConfiguration.wrap(json.loads(f.read())['config'])
            cls.named_expressions = cls.data_source.named_expression_objects

    def setUp(self):
        self.orig_db = CommCareCase.get_db()
        self.database = FakeCouchDb()
        CommCareCase.set_db(self.database)

    def tearDown(self):
        CommCareCase.set_db(self.orig_db)

    def get_column(self, column_id):
        return [
            ind
            for ind in self.data_source.configured_indicators
            if ind['column_id'] == column_id
        ][0]
