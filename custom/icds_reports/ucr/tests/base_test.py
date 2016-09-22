import os
import mock
from xml.etree import ElementTree
from django.test import TestCase
from casexml.apps.case.mock import CaseFactory
from corehq.util.test_utils import TestFileMixin
from corehq.apps.userreports.sql import IndicatorSqlAdapter
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.form_processor.tests.utils import FormProcessorTestUtils


def _safe_text(input_value):
    if input_value is None:
        return ''
    try:
        return str(input_value)
    except:
        return ''


def create_element_with_value(element_name, value):
    elem = ElementTree.Element(element_name)
    elem.text = _safe_text(value)
    return elem


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

    @classmethod
    def tearDownClass(cls):
        super(BaseICDSDatasourceTest, cls).tearDownClass()
        cls._call_center_domain_mock.stop()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()

    def _rebuild_table_get_query_object(self):
        rebuild_indicators(self.datasource._id)
        adapter = IndicatorSqlAdapter(self.datasource)
        return adapter.get_query_object()
