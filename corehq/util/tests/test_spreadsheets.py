from django.test import SimpleTestCase


class IteratorJSONReaderTest(SimpleTestCase):
    def test(self):
        from corehq.util.spreadsheets.excel import IteratorJSONReader

        def normalize(it):
            r = []
            for row in IteratorJSONReader(it):
                r.append(sorted(row.items()))
            return r

        self.assertEquals(normalize([]), [])

        self.assertEquals(
            normalize([['A', 'B', 'C'], ['1', '2', '3']]),
            [[('A', '1'), ('B', '2'), ('C', '3')]]
        )

        self.assertEquals(
            normalize([['A', 'data: key', 'user 1', 'user 2', 'is-ok?'],
                       ['1', '2', '3', '4', 'yes']]),
            [[('A', '1'), ('data', {'key': '2'}), ('is-ok', True),
              ('user', ['3', '4'])]]
        )
