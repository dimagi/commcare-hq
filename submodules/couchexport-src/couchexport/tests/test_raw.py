from StringIO import StringIO
import json
from django.test import TestCase
import itertools
from couchexport.export import export_raw, export_from_tables
from couchexport.models import Format

class ExportRawTest(TestCase):

    def test_export_raw(self):
        headers = (('people', ('name', 'gender')), ('offices', ('location', 'name')))
        data = (
            ('people', [('danny', 'male'), ('amelia', 'female'), ('carter', 'various')]),
            ('offices', [('Delhi, India', 'DSI'), ('Boston, USA', 'Dimagi, Inc'), ('Capetown, South Africa', 'DSA')])
        )
        EXPECTED = {"offices": {"headers": ["location", "name"], "rows": [["Delhi, India", "DSI"], ["Boston, USA", "Dimagi, Inc"], ["Capetown, South Africa", "DSA"]]}, "people": {"headers": ["name", "gender"], "rows": [["danny", "male"], ["amelia", "female"], ["carter", "various"]]}}

        that = self
        class Tester(object):
            def __enter__(self):
                self.buffer = StringIO()
                return self.buffer
            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    that.assertDictEqual(json.loads(self.buffer.getvalue()), EXPECTED)
                self.buffer.close()

        with Tester() as buffer:
            export_raw(headers, data, buffer, format=Format.JSON)

        with Tester() as buffer:
            # test lists
            export_raw(list(headers), list(data), buffer, format=Format.JSON)

        with Tester() as buffer:
            # test generators
            export_raw((h for h in headers), ((name, (r for r in rows)) for name, rows in data), buffer, format=Format.JSON)
            
        with Tester() as buffer:
            # test export_from_tables
            headers = dict(headers)
            data = dict(data)
            tables = {}
            for key in set(headers.keys()) | set(data.keys()):
                tables[key] = itertools.chain([headers[key]], data[key])

            export_from_tables(tables.items(), buffer, format=Format.JSON)
