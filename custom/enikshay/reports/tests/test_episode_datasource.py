import os
import mock
from datetime import datetime

from django.test import TestCase
from corehq.util.test_utils import TestFileMixin
from corehq.form_processor.tests.utils import FormProcessorTestUtils

from corehq.apps.userreports.sql import IndicatorSqlAdapter
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.tasks import rebuild_indicators
from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex


class BaseEnikshayDatasourceTest(TestCase, TestFileMixin):
    dependent_apps = ['corehq.apps.domain', 'corehq.apps.case']
    file_path = ('data_sources', )
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))
    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )
    datasource_filename = ''

    @classmethod
    def setUpClass(cls):
        super(BaseEnikshayDatasourceTest, cls).setUpClass()
        cls._call_center_domain_mock.start()
        cls.static_datasource = StaticDataSourceConfiguration.wrap(
            cls.get_json(cls.datasource_filename)
        )
        cls.domain = cls.static_datasource.domains[0]
        cls.datasource = StaticDataSourceConfiguration._get_datasource_config(
            cls.static_datasource,
            cls.domain,
        )
        cls.factory = CaseFactory(domain=cls.domain)

    @classmethod
    def tearDownClass(cls):
        super(BaseEnikshayDatasourceTest, cls).tearDownClass()
        cls._call_center_domain_mock.stop()

    def setUp(self):
        super(BaseEnikshayDatasourceTest, self).setUp()
        self._create_case_structure()
        self.query = self._rebuild_table_get_query_object()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()

    def _rebuild_table_get_query_object(self):
        rebuild_indicators(self.datasource._id)
        adapter = IndicatorSqlAdapter(self.datasource)
        return adapter.get_query_object()


class TestEpisodeDatasource(BaseEnikshayDatasourceTest):
    datasource_filename = 'episode'

    def _create_case_structure(self):
        person = CaseStructure(
            case_id='person',
            attrs={
                "case_type": "person",
                "create": True,
                "update": dict(
                    dob="1987-08-15",
                    sex="m",
                )
            },
        )
        episode = CaseStructure(
            case_id='episode_case_1',
            attrs={
                'create': True,
                'case_type': 'episode',
                "update": dict(
                    person_name="Ramsey Bolton",
                    disease_classification="pulmonary",
                    person_id="person",
                    opened_on=datetime(1989, 6, 11, 0, 0),
                    patient_type="new",
                    hiv_status="reactive"
                )
            },
            indices=[CaseIndex(
                person,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=person.attrs['case_type'],
            )],
        )
        self.factory.create_or_update_cases([episode])

    def test_indicators(self):
        self.assertEqual(self.query.count(), 1)
        row = self.query.first()

        self.assertEqual(row.male, 1)
        self.assertEqual(row.female, 0)
        self.assertEqual(row.transgender, 0)

        self.assertEqual(row.disease_classification, 'pulmonary')
        self.assertEqual(row.hiv_positive, 1)

        self.assertEqual(row.age_in_days, 666)
        self.assertEqual(row.under_15, 1)

        self.assertEqual(row.new_smear_positive_pulmonary_TB_under_15, 1)
        self.assertEqual(row.new_smear_positive_pulmonary_TB_over_15, 0)
