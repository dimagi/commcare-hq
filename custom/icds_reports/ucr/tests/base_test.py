import os
import mock
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from xml.etree import cElementTree as ElementTree
from django.test import TestCase
from casexml.apps.case.mock import CaseFactory
from corehq.util.test_utils import TestFileMixin
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.tasks import _iteratively_build_table, queue_async_indicators
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


es_form_cache = []


def mget_query_fake(index, ids, source):
    return [
        {'_id': form['_id'], '_source': form}
        for form in es_form_cache
        if form['_id'] in ids
    ]


@mock.patch('custom.icds_reports.ucr.expressions.mget_query', mget_query_fake)
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
        cls.adapter = get_indicator_adapter(cls.datasource)
        cls.adapter.rebuild_table()

    @classmethod
    def tearDownClass(cls):
        cls._call_center_domain_mock.stop()
        cls.adapter.drop_table()
        super(BaseICDSDatasourceTest, cls).tearDownClass()

    def tearDown(self):
        global es_form_cache
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.adapter.clear_table()
        es_form_cache = []

    def _get_query_object(self):
        return self.adapter.get_query_object()

    def _run_iterative_monthly_test(self, case_id, cases):
        start_date = date(2016, 2, 1)
        with mock.patch('custom.icds_reports.ucr.expressions._datetime_now') as now:
            now.return_value = datetime.combine(start_date, datetime.min.time()) + relativedelta(months=1)
            _iteratively_build_table(self.datasource)
            queue_async_indicators()
        query = self._get_query_object().filter_by(doc_id=case_id).order_by(self.adapter.get_table().columns.month)
        self.assertEqual(query.count(), len(cases))

        for index, test_values in cases:
            row = query.all()[index]._asdict()
            self.assertEqual(row['month'], start_date + relativedelta(months=index))
            for key, exp_value in test_values:
                self.assertEqual(exp_value, row[key],
                                 str(index) + ":" + key + ' ' + str(exp_value) + ' != ' + str(row[key]))

    def _submit_form(self, form):
        global es_form_cache
        submitted_form = submit_form_locally(ElementTree.tostring(form), self.domain, **{})
        es_form_cache.append(submitted_form.xform.to_json())
