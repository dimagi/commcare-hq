import os
import mock
from datetime import date
from dateutil.relativedelta import relativedelta
from xml.etree import ElementTree
from django.test import TestCase
from casexml.apps.case.mock import CaseFactory
from corehq.util.test_utils import TestFileMixin
from corehq.apps.userreports.sql import IndicatorSqlAdapter
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.tasks import iteratively_build_table
from corehq.form_processor.tests.utils import FormProcessorTestUtils


def _safe_text(input_value):
    if input_value is None:
        return ''
    try:
        return str(input_value)
    except:
        return ''


def add_element(element, element_name, value):
    if value is not None:
        elem = ElementTree.Element(element_name)
        elem.text = _safe_text(value)
        element.append(elem)


class BaseICDSDatasourceTest(TestCase, TestFileMixin):
    dependent_apps = ['corehq.apps.domain', 'corehq.apps.case']
    file_path = ('data_sources', )
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))
    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )
    datasource_filename = ''

    @classmethod
    def setUpClass(cls):
        super(BaseICDSDatasourceTest, cls).setUpClass()
        cls._call_center_domain_mock.start()
        cls.static_datasource = StaticDataSourceConfiguration.wrap(
            cls.get_json(cls.datasource_filename)
        )
        cls.domain = cls.static_datasource.domains[0]
        cls.datasource = StaticDataSourceConfiguration._get_datasource_config(
            cls.static_datasource,
            cls.domain,
        )
        cls.casefactory = CaseFactory(domain=cls.domain)
        adapter = IndicatorSqlAdapter(cls.datasource)
        adapter.build_table()

    @classmethod
    def tearDownClass(cls):
        cls._call_center_domain_mock.stop()
        adapter = IndicatorSqlAdapter(cls.datasource)
        adapter.drop_table()
        super(BaseICDSDatasourceTest, cls).tearDownClass()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        adapter = IndicatorSqlAdapter(self.datasource)
        adapter.clear_table()

    def _get_query_object(self):
        adapter = IndicatorSqlAdapter(self.datasource)
        return adapter.get_query_object()

    def _run_iterative_monthly_test(self, case_id, cases, start_date=date(2015, 12, 1)):
        iteratively_build_table(self.datasource)
        query = self._get_query_object().filter_by(doc_id=case_id)
        self.assertEqual(query.count(), 7)

        for index, test_values in cases:
            row = query.all()[index]._asdict()
            self.assertEqual(row['month'], start_date + relativedelta(months=index))
            for key, exp_value in test_values:
                self.assertEqual(exp_value, row[key],
                                 str(index) + ":" + key + ' ' + str(exp_value) + ' != ' + str(row[key]))
