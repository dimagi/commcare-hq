import uuid
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
        self._resume_helper.clear_ids()

    def test_set_ids(self):
        ids = [uuid.uuid4().hex for i in range(5)]
        self._resume_helper.set_ids_to_resume_from(ids)
        self.assertEqual(ids, self._resume_helper.get_ids_to_resume_from())

    def test_remove_id(self):
        ids = [uuid.uuid4().hex for i in range(5)]
        self._resume_helper.set_ids_to_resume_from(ids)
        self._resume_helper.remove_id(ids[0])
        self.assertEqual(ids[1:], self._resume_helper.get_ids_to_resume_from())
        self._resume_helper.remove_id(ids[4])
        self.assertEqual(ids[1:4], self._resume_helper.get_ids_to_resume_from())

    def test_add_id_to_nothing(self):
        doc_id = uuid.uuid4().hex
        self._resume_helper.add_id(doc_id)
        self.assertEqual([doc_id], self._resume_helper.get_ids_to_resume_from())

    def test_add_id_to_list(self):
        ids = [uuid.uuid4().hex for i in range(5)]
        self._resume_helper.set_ids_to_resume_from(ids)
        doc_id = uuid.uuid4().hex
        self._resume_helper.add_id(doc_id)
        self.assertEqual(ids + [doc_id], self._resume_helper.get_ids_to_resume_from())

    def test_clear_ids(self):
        ids = [uuid.uuid4().hex for i in range(5)]
        self._resume_helper.set_ids_to_resume_from(ids)
        self._resume_helper.clear_ids()
        self.assertEqual([], self._resume_helper.get_ids_to_resume_from())

    def test_has_resume_info_false(self):
        self.assertEqual(False, self._resume_helper.has_resume_info())

    def test_has_resume_info_true(self):
        self._resume_helper.set_ids_to_resume_from([uuid.uuid4().hex for i in range(5)])
        self.assertEqual(True, self._resume_helper.has_resume_info())
