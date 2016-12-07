from django.test import TestCase
from corehq.apps.case_importer.tracking.filestorage import write_case_import_file, \
    read_case_import_file


class FilestorageTest(TestCase):

    def test_write_read_from_file(self):
        filename = '/tmp/test_file.txt'
        content = 'this is the message\n'

        with open(filename, 'w') as f:
            f.write(content)

        with open(filename, 'r') as f:
            identifier = write_case_import_file(f)

        self.assertEqual(read_case_import_file(identifier).read(), content)
        self.assertEqual(''.join(read_case_import_file(identifier)), content)
