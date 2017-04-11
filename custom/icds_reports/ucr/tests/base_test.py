import os
import mock
from datetime import date
from dateutil.relativedelta import relativedelta
from xml.etree import ElementTree
from django.test import TestCase
from casexml.apps.case.mock import CaseFactory
from corehq.apps.es.fake.forms_fake import FormESFake
from corehq.util.test_utils import TestFileMixin
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.userreports.util import get_indicator_adapter
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


@mock.patch('custom.icds_reports.ucr.expressions.FormES', FormESFake)
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
        cls.adapter = get_indicator_adapter(cls.datasource, can_handle_laboratory=True)
        cls.adapter.rebuild_table()

    @classmethod
    def tearDownClass(cls):
        cls._call_center_domain_mock.stop()
        cls.adapter.drop_table()
        super(BaseICDSDatasourceTest, cls).tearDownClass()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.adapter.clear_table()
        FormESFake.reset_docs()

    def _get_query_object(self):
        return self.adapter.get_query_object()

    def _run_iterative_monthly_test(self, case_id, cases, start_date=date(2015, 12, 1)):
        iteratively_build_table(self.datasource)
        # TODO(Sheel/J$) filter_by does not work on ES
        query = self._get_query_object().filter_by(doc_id=case_id)
        self.assertEqual(query.count(), 7)

        for index, test_values in cases:
            row = query.all()[index]._asdict()
            self.assertEqual(row['month'], start_date + relativedelta(months=index))
            for key, exp_value in test_values:
                self.assertEqual(exp_value, row[key],
                                 str(index) + ":" + key + ' ' + str(exp_value) + ' != ' + str(row[key]))

    def _submit_form(self, form):
        submitted_form = submit_form_locally(ElementTree.tostring(form), self.domain, **{})
        FormESFake.save_doc(submitted_form.xform.to_json())
