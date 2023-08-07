from django.test import SimpleTestCase

from corehq.apps.userreports.rebuild import DataSourceResumeHelper
from corehq.apps.userreports.tests.utils import get_sample_data_source
from corehq.tests.locks import real_redis_client


class DataSourceResumeBuildTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(DataSourceResumeBuildTest, cls).setUpClass()
        cls._data_source = get_sample_data_source()
        with real_redis_client():
            cls._resume_helper = DataSourceResumeHelper(cls._data_source)

    def setUp(self):
        super(DataSourceResumeBuildTest, self).setUp()
        self._resume_helper.clear_resume_info()

    def test_add_types(self):
        self.assertEqual([], self._resume_helper.get_completed_iterations())

        case_type = 'type1'
        self._resume_helper.add_completed_iteration("domain1", case_type)
        self.assertEqual([["domain1", case_type]], self._resume_helper.get_completed_iterations())

        case_type_2 = 'type2'
        self._resume_helper.add_completed_iteration("domain1", case_type_2)
        self.assertEqual(
            [["domain1", case_type], ["domain1", case_type_2]],
            self._resume_helper.get_completed_iterations()
        )

    def test_clear_resume_info(self):
        self._resume_helper.add_completed_iteration("domain1", 'type1')
        self._resume_helper.clear_resume_info()
        self.assertEqual([], self._resume_helper.get_completed_iterations())

    def test_has_resume_info_false(self):
        self.assertEqual(False, self._resume_helper.has_resume_info())

    def test_has_resume_info_true(self):
        self._resume_helper.add_completed_iteration("domain1", 'type1')
        self.assertEqual(True, self._resume_helper.has_resume_info())
