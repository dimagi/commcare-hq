from io import BytesIO
from itertools import zip_longest

from django.test import SimpleTestCase

from couchexport.export import export_raw
from couchexport.models import Format

from ..upload.workbook import get_workbook


class TestFixtureWorkbook(SimpleTestCase):

    def test_get_owners(self):
        workbook = self.get_workbook({
            'types': [
                ('Delete(Y/N)', 'table_id', 'is_global?', 'field 1'),
                ('N', 'things', 'no', 'name'),
            ],
            'things': [
                ('UID', 'Delete(Y/N)', 'field: name', 'user 1', 'group 1', 'location 1'),
                (None, 'N', 'apple', 'user1', None, None),
                (None, 'N', 'banana', None, 'g1', None),
                (None, 'N', 'coconut', 'user2', None, 'loc1'),
            ]
        })
        all_owners = workbook.get_owners()
        self.assertEqual(all_owners, {
            "user": {"user1", "user2"},
            "group": {"g1"},
            "location": {"loc1"},
        })

        # must be able to iterate tables and rows after retrieving owners
        expected_owners = [
            {"user": ["user1"], "group": [], "location": []},
            {"user": [], "group": ["g1"], "location": []},
            {"user": ["user2"], "group": [], "location": ["loc1"]},
        ]
        table = next(workbook.iter_tables("test"))
        rows = workbook.iter_rows(table, {})
        for row, expected in zip_longest(rows, expected_owners):
            ownerships = list(workbook.iter_ownerships(row, row._id, OWNER_IDS))
            actual = map_ownerships(ownerships)
            self.assertEqual(actual, expected)

    def get_workbook(self, data):
        headers = [(key, rows[0]) for key, rows in data.items()]
        rows = [(key, rows[1:]) for key, rows in data.items()]
        file = BytesIO()
        export_raw(headers, rows, file, format=Format.XLS_2007)
        return get_workbook(file)


def map_ownerships(ownerships):
    return {
        owner_type: [
            OWNERS_BY_ID[ownership.owner_id]
            for ownership in ownerships
            if ownership.owner_type == owner_type
        ]
        for owner_type in ["user", "group", "location"]
    }


OWNER_IDS = {
    "user": {"user1": "abc", "user2": "jkl"},
    "group": {"g1": "def"},
    "location": {"loc1": "ghi"},
}
OWNERS_BY_ID = {"abc": "user1", "def": "g1", "ghi": "loc1", "jkl": "user2"}
