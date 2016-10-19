import os
import mock
from datetime import datetime

from django.test import TestCase
from corehq.util.test_utils import TestFileMixin
from corehq.form_processor.tests.utils import FormProcessorTestUtils

from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.userreports.tests.utils import run_with_all_ucr_backends
from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex


class BaseEnikshayDatasourceTest(TestCase, TestFileMixin):
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

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()

    def _rebuild_table_get_query_object(self):
        rebuild_indicators(self.datasource._id)
        adapter = get_indicator_adapter(self.datasource)
        adapter.refresh_table()
        return adapter.get_query_object()


class TestEpisodeDatasource(BaseEnikshayDatasourceTest):
    datasource_filename = 'episode'

    def _create_case_structure(self, lab_result="TB detected", disease_classification="pulmonary"):
        person = CaseStructure(
            case_id='person',
            attrs={
                "case_type": "person",
                "create": True,
                "update": dict(
                    dob="1987-08-15",
                    sex="male",
                )
            },
        )

        occurrence = CaseStructure(
            case_id='occurrence',
            attrs={
                "case_type": "occurrence",
                "create": True,
                'update': dict(
                    hiv_status='reactive'
                )
            },
            indices=[
                CaseIndex(
                    person,
                    identifier='host',
                    relationship=CASE_INDEX_EXTENSION,
                    related_type=person.attrs['case_type']
                )
            ]
        )

        test = CaseStructure(
            case_id='test',
            attrs={
                'case_type': 'test',
                'create': True,
                'update': dict(
                    test_type_value='microscopy-zn',
                    result=lab_result,
                    purpose_of_testing='diagnostic'
                )
            },
            indices=[CaseIndex(
                occurrence,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=occurrence.attrs['case_type'],
            )]
        )

        episode = CaseStructure(
            case_id='episode_case_1',
            attrs={
                'create': True,
                'case_type': 'episode',
                "update": dict(
                    person_name="Ramsey Bolton",
                    disease_classification=disease_classification,
                    person_id="person",
                    opened_on=datetime(1989, 6, 11, 0, 0),
                    patient_type="new",
                    hiv_status="reactive",
                    lab_result=lab_result
                )
            },
            indices=[CaseIndex(
                occurrence,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=occurrence.attrs['case_type'],
            )],
        )
        self.factory.create_or_update_cases([episode, test])

    @run_with_all_ucr_backends
    def test_hiv_status(self):
        self._create_case_structure()
        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 1)
        row = query[0]

        self.assertEqual(row.hiv_status, 'reactive')

    @run_with_all_ucr_backends
    def test_sputum_positive(self):
        self._create_case_structure(lab_result="tb_detected")
        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 1)
        row = query[0]

        self.assertEqual(row.male, 1)
        self.assertEqual(row.female, 0)
        self.assertEqual(row.transgender, 0)

        self.assertEqual(row.disease_classification, 'pulmonary')
        self.assertEqual(row.hiv_positive, 1)

        self.assertEqual(row.age_in_days, 666)
        self.assertEqual(row.under_15, 1)

        self.assertEqual(row.new_smear_positive_pulmonary_TB, 1)
        self.assertEqual(row.new_smear_positive_pulmonary_TB_male, 1)
        self.assertEqual(row.new_smear_positive_pulmonary_TB_female, 0)
        self.assertEqual(row.new_smear_positive_pulmonary_TB_transgender, 0)

        self.assertEqual(row.new_smear_positive_pulmonary_TB_under_15, 1)
        self.assertEqual(row.new_smear_positive_pulmonary_TB_over_15, 0)

    @run_with_all_ucr_backends
    def test_sputum_negative(self):
        self._create_case_structure(lab_result="tb_not_detected")
        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 1)
        row = query[0]

        self.assertEqual(row.new_smear_negative_pulmonary_TB, 1)
        self.assertEqual(row.new_smear_negative_pulmonary_TB_male, 1)
        self.assertEqual(row.new_smear_negative_pulmonary_TB_female, 0)
        self.assertEqual(row.new_smear_negative_pulmonary_TB_transgender, 0)

        self.assertEqual(row.new_smear_negative_pulmonary_TB_under_15, 1)
        self.assertEqual(row.new_smear_negative_pulmonary_TB_over_15, 0)

    @run_with_all_ucr_backends
    def test_extra_pulmonary(self):
        self._create_case_structure(lab_result="tb_detected", disease_classification="extra_pulmonary")
        query = self._rebuild_table_get_query_object()
        self.assertEqual(query.count(), 1)
        row = query[0]

        self.assertEqual(row.new_smear_positive_extra_pulmonary_TB, 1)
        self.assertEqual(row.new_smear_positive_extra_pulmonary_TB_male, 1)
        self.assertEqual(row.new_smear_positive_extra_pulmonary_TB_female, 0)
        self.assertEqual(row.new_smear_positive_extra_pulmonary_TB_transgender, 0)

        self.assertEqual(row.new_smear_positive_extra_pulmonary_TB_under_15, 1)
        self.assertEqual(row.new_smear_positive_extra_pulmonary_TB_over_15, 0)
