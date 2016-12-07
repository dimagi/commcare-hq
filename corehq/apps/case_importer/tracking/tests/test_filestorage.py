from django.test import TestCase
from corehq.apps.case_importer.tracking.filestorage import transient_file_store, persistent_file_store
from corehq.util.files import file_extention_from_filename


class FilestorageTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.filename = '/tmp/test_file.txt'
        cls.content = 'this is the message\n'

        with open(cls.filename, 'w') as f:
            f.write(cls.content)

    @classmethod
    def tearDownClass(cls):
        pass

    def test_transient(self):
        with open(self.filename, 'r') as f:
            identifier = transient_file_store.write_file(f, 'test_file.txt')

        tmpfile = transient_file_store.get_tempfile(identifier)
        self.assertEqual(file_extention_from_filename(tmpfile), '.txt')
        with open(tmpfile) as f:
            self.assertEqual(f.read(), self.content)

    def test_persistent(self):
        with open(self.filename, 'r') as f:
            identifier = persistent_file_store.write_file(f, 'test_file.txt')

        tmpfile = persistent_file_store.get_tempfile(identifier)
        self.assertEqual(file_extention_from_filename(tmpfile), '.txt')
        with open(tmpfile) as f:
            self.assertEqual(f.read(), self.content)
