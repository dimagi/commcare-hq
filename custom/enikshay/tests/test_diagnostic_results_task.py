from mock import patch, MagicMock
from django.test import TestCase, override_settings

from custom.enikshay.tasks import EpisodeTestUpdate
from custom.enikshay.tests.utils import ENikshayCaseStructureMixin


@patch('corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider', MagicMock())
@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestDiagnosticInvestigationsTask(ENikshayCaseStructureMixin, TestCase):
    def setUp(self):
        super(TestDiagnosticInvestigationsTask, self).setUp()
        self.cases = self.create_case_structure()
        self.updater = EpisodeTestUpdate(self.domain, self.cases[self.episode_id])

    def test_diagnostic_update(self):
        self.create_test_case(self.occurrence_id, {
            'enrolled_in_private': 'true',
            'date_reported': '2017-08-13',
            'purpose_of_test': 'diagnostic',
            'investigation_id': 'ABC-ABC-ABC',
            'result_grade': 'TB Not Detected: scanty'
        })
        self.create_test_case(self.occurrence_id, {
            'enrolled_in_private': 'true',
            'date_reported': '2017-08-14',
            'purpose_of_test': 'diagnostic',
            'investigation_id': 'DEF-DEF-DEF',
            'result_grade': 'TB Detected: 3+ scanty',
        })
        self.create_test_case(self.occurrence_id, {
            'enrolled_in_private': 'true',
            'date_reported': '2017-08-15',
            'purpose_of_test': 'followup',
            'investigation_id': 'DEF-BCD-DEF',
            'result_grade': 'TB Detected: 3+ scanty',
        })

        expected = {
            'diagnostic_tests': u'ABC-ABC-ABC, DEF-DEF-DEF',
            'diagnostic_test_results': u'TB Not Detected: scanty, TB Detected: 3+ scanty'
        }

        self.assertDictEqual(
            expected,
            self.updater.update_json()
        )

    def test_no_update(self):
        self.create_test_case(self.occurrence_id, {
            'enrolled_in_private': 'true',
            'date_reported': '2017-08-15',
            'purpose_of_test': 'followup',
            'investigation_id': 'DEF-BCD-DEF',
            'result_grade': 'TB Detected: 3+ scanty',
        })
        self.assertDictEqual({}, self.updater.update_json())
