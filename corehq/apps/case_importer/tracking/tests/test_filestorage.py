from django.test import TestCase
from corehq.apps.case_importer.tracking.filestorage import transient_file_store, persistent_file_store
from corehq.util.files import file_extention_from_filename
from corehq.util.test_utils import generate_cases


class FilestorageTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(FilestorageTest, cls).setUpClass()
        cls.filename = '/tmp/test_file.txt'
        cls.content = 'this is the message\n'

        with open(cls.filename, 'w') as f:
            f.write(cls.content)


@generate_cases([(transient_file_store,),
                 (persistent_file_store,)], FilestorageTest)
def test_transient(self, file_store):
    with open(self.filename, 'r') as f:
        identifier = file_store.write_file(f, 'test_file.txt').identifier

    tmpfile = file_store.get_tempfile_ref_for_contents(identifier)
    self.assertEqual(file_extention_from_filename(tmpfile), '.txt')
    with open(tmpfile) as f:
        self.assertEqual(f.read(), self.content)

    self.assertEqual(file_store.get_filename(identifier), 'test_file.txt')
