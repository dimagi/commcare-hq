from django.test import SimpleTestCase
from corehq.util.spreadsheets.excel import IteratorJSONReader


class IteratorJSONReaderTest(SimpleTestCase):

    @staticmethod
    def normalize(it):
        r = []
        for row in IteratorJSONReader(it):
            r.append(sorted(row.items()))
        return r

    def test_basic(self):
        self.assertEquals(self.normalize([]), [])

        self.assertEquals(
            self.normalize([['A', 'B', 'C'], ['1', '2', '3']]),
            [[('A', '1'), ('B', '2'), ('C', '3')]]
        )

        self.assertEquals(
            self.normalize([['A', 'data: key', 'user 1', 'user 2', 'is-ok?'],
                       ['1', '2', '3', '4', 'yes']]),
            [[('A', '1'), ('data', {'key': '2'}), ('is-ok', True),
              ('user', ['3', '4'])]]
        )

    def test_list_headers_without_number(self):
        self.assertEquals(
            self.normalize([['A', 'data: key', 'user', 'user 2', 'is-ok?'],
                       ['1', '2', '3', '4', 'yes']]),
            [[('A', '1'), ('data', {'key': '2'}), ('is-ok', True),
              ('user', ['3', '4'])]]
        )
