from __future__ import absolute_import
from django.test import SimpleTestCase
from corehq.apps.userreports.rebuild import DataSourceResumeHelper
from corehq.apps.userreports.tests.utils import get_sample_data_source


class DataSourceResumeBuildTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(DataSourceResumeBuildTest, cls).setUpClass()
        cls._data_source = get_sample_data_source()
        cls._resume_helper = DataSourceResumeHelper(cls._data_source)

    def setUp(self):
        super(DataSourceResumeBuildTest, self).setUp()
        self._resume_helper.clear_resume_info()

    def test_add_types(self):
        self.assertEqual([], self._resume_helper.get_completed_case_type_or_xmlns())

        case_type = 'type1'
        self._resume_helper.add_completed_case_type_or_xmlns(case_type)
        self.assertEqual([case_type], self._resume_helper.get_completed_case_type_or_xmlns())

        case_type_2 = 'type2'
        self._resume_helper.add_completed_case_type_or_xmlns(case_type_2)
        self.assertEqual([case_type, case_type_2], self._resume_helper.get_completed_case_type_or_xmlns())

    def test_clear_resume_info(self):
        self._resume_helper.add_completed_case_type_or_xmlns('type1')
        self._resume_helper.clear_resume_info()
        self.assertEqual([], self._resume_helper.get_completed_case_type_or_xmlns())

    def test_has_resume_info_false(self):
        self.assertEqual(False, self._resume_helper.has_resume_info())

    def test_has_resume_info_true(self):
        self._resume_helper.add_completed_case_type_or_xmlns('type1')
        self.assertEqual(True, self._resume_helper.has_resume_info())
