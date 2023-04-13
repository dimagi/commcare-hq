from io import BytesIO
from unittest.mock import patch

from django.test import TestCase

from testil import eq, Regex

from couchexport.export import export_raw
from couchexport.models import Format

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.users.models import CommCareUser

from .. import download as mod
from ..models import LookupTable, LookupTableRow, OwnerType, TypeField
from ..upload.run_upload import _run_upload
from ..upload.workbook import get_workbook


class TestLookupTableOwners(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        publish = patch("corehq.apps.locations.document_store.publish_location_saved")
        publish.start()
        cls.addClassCleanup(publish.stop)

        cls.domain = 'fixture-upload-test'
        cls.project = create_domain(cls.domain)
        cls.addClassCleanup(cls.project.delete)

        cls.user1 = CommCareUser.create(
            cls.domain, f"user1@{cls.domain}.commcarehq.org", "pass", None, None)
        cls.addClassCleanup(cls.user1.delete, cls.domain, deleted_by=None)
        cls.user2 = CommCareUser.create(
            cls.domain, f"user2@{cls.domain}.commcarehq.org", "pass", None, None)
        cls.addClassCleanup(cls.user2.delete, cls.domain, deleted_by=None)
        cls.user3 = CommCareUser.create(
            cls.domain, f"3@{cls.domain}.commcarehq.org", "pass", None, None)
        cls.addClassCleanup(cls.user3.delete, cls.domain, deleted_by=None)

        # group names are case sensitive, user and location names are not
        cls.group1 = Group(domain=cls.domain, name="G1", users=[cls.user1._id])
        cls.group1.save()
        cls.addClassCleanup(cls.group1.delete)
        cls.group2 = Group(domain=cls.domain, name="g2", users=[cls.user1._id])
        cls.group2.save()
        cls.addClassCleanup(cls.group2.delete)
        cls.group3 = Group(domain=cls.domain, name="3", users=[cls.user1._id])
        cls.group3.save()
        cls.addClassCleanup(cls.group3.delete)

        cls.region = LocationType(domain=cls.domain, name="region", code="region")
        cls.region.save()
        cls.loc1 = SQLLocation(domain=cls.domain, name="loc1", location_type=cls.region)
        cls.loc1.save()
        cls.loc2 = SQLLocation(domain=cls.domain, name="loc2", location_type=cls.region)
        cls.loc2.save()
        cls.loc3 = SQLLocation(domain=cls.domain, name="3", location_type=cls.region)
        cls.loc3.save()

    def test_download(self):
        self.upload([
            (None, 'N', 'apple', 'user1', 'G1', 'loc1'),
            (None, 'N', 'banana', '', 'g2', 'loc2'),
            (None, 'N', 'coconut', '', '', '3'),
        ])
        data = self.prepare_download(['things'])
        self.assertEqual(data["things"]["type"], {
            'Delete(Y/N)': 'N',
            'table_id': 'things',
            'is_global?': 'no',
            'field 1': 'name',
        })
        self.assertEqual(data["things"]["rows"], [
            {
                'Delete(Y/N)': 'N',
                'UID': Regex(r"^[0-9a-f]{32}$"),
                'field: name': 'apple',
                'group 1': 'G1',
                'location 1': 'loc1',
                'user 1': 'user1',
            }, {
                'Delete(Y/N)': 'N',
                'UID': Regex(r"^[0-9a-f]{32}$"),
                'field: name': 'banana',
                'group 1': 'g2',
                'location 1': 'loc2',
                'user 1': '',
            }, {
                'Delete(Y/N)': 'N',
                'UID': Regex(r"^[0-9a-f]{32}$"),
                'field: name': 'coconut',
                'group 1': '',
                'location 1': '3',
                'user 1': '',
            }
        ])

    def test_count(self):
        self.upload([
            (None, 'N', 'apple', 'user1', 'G1', 'loc1'),
            (None, 'N', 'banana', '', 'g2', 'loc2'),
            (None, 'N', 'coconut', '', '', '3'),
        ])
        table = LookupTable.objects.get(domain=self.domain, tag='things')
        rows = list(LookupTableRow.objects.iter_rows(self.domain, tag='things'))
        names = mod.OwnerNames([table])
        self.assertEqual(sum(names.count(r, OwnerType.User) for r in rows), 1)
        self.assertEqual(sum(names.count(r, OwnerType.Group) for r in rows), 2)
        self.assertEqual(sum(names.count(r, OwnerType.Location) for r in rows), 3)

    def test_get_usernames(self):
        headers = (
            self.headers[0],
            ('things', ('UID', 'Delete(Y/N)', 'field: name', 'user 1', 'user 2')),
        )
        data = self.make_rows([
            (None, 'N', 'apple', 'user1', '3'),
            (None, 'N', 'banana', 'user2'),
            (None, 'N', 'banana', '3'),
        ])
        workbook = self.get_workbook_from_data(headers, data)
        result = _run_upload(self.domain, workbook)
        self.check_upload_result(result)
        table = LookupTable.objects.get(domain=self.domain, tag='things')
        rows = list(LookupTableRow.objects.iter_rows(self.domain, tag='things'))
        names = mod.OwnerNames([table])
        self.assertEqual(names.get_usernames(rows[0]), ['3', 'user1'])
        self.assertEqual(names.get_usernames(rows[1]), ['user2'])
        self.assertEqual(names.get_usernames(rows[2]), ['3'])
        self.assertEqual(len(rows), 3)

    def test_get_group_names(self):
        headers = (
            self.headers[0],
            ('things', ('UID', 'Delete(Y/N)', 'field: name', 'group 1', 'group 2')),
        )
        data = self.make_rows([
            (None, 'N', 'apple', 'G1', '3'),
            (None, 'N', 'banana', 'g2'),
            (None, 'N', 'banana', '3'),
        ])
        workbook = self.get_workbook_from_data(headers, data)
        result = _run_upload(self.domain, workbook)
        self.check_upload_result(result)
        table = LookupTable.objects.get(domain=self.domain, tag='things')
        rows = list(LookupTableRow.objects.iter_rows(self.domain, tag='things'))
        names = mod.OwnerNames([table])
        self.assertEqual(names.get_group_names(rows[0]), ['3', 'G1'])
        self.assertEqual(names.get_group_names(rows[1]), ['g2'])
        self.assertEqual(names.get_group_names(rows[2]), ['3'])
        self.assertEqual(len(rows), 3)

    def test_get_location_names(self):
        headers = (
            self.headers[0],
            ('things', ('UID', 'Delete(Y/N)', 'field: name', 'location 1', 'location 2')),
        )
        data = self.make_rows([
            (None, 'N', 'apple', 'Loc1', '3'),
            (None, 'N', 'banana', 'LOC2'),
            (None, 'N', 'banana', '3'),
        ])
        workbook = self.get_workbook_from_data(headers, data)
        result = _run_upload(self.domain, workbook)
        self.check_upload_result(result)
        table = LookupTable.objects.get(domain=self.domain, tag='things')
        rows = list(LookupTableRow.objects.iter_rows(self.domain, tag='things'))
        names = mod.OwnerNames([table])
        self.assertEqual(names.get_location_codes(rows[0]), ['3', 'loc1'])
        self.assertEqual(names.get_location_codes(rows[1]), ['loc2'])
        self.assertEqual(names.get_location_codes(rows[2]), ['3'])
        self.assertEqual(len(rows), 3)

    def test_with_missing_owners(self):
        self.upload([
            (None, 'N', 'apple', 'user1', 'G1', 'loc1'),
            (None, 'N', 'banana', '', 'g2', 'loc2'),
            (None, 'N', 'coconut', '', '', '3'),
        ])
        table = LookupTable.objects.get(domain=self.domain, tag='things')
        rows = list(LookupTableRow.objects.iter_rows(self.domain, tag='things'))
        names = mod.OwnerNames([table])

        # simulate owners that have been deleted, but are still present in LookupTableRowOwner
        banana = {r.fields["name"][0].value: r for r in rows}["banana"]
        names.owners[banana.id][OwnerType.User].add("xu")
        names.owners[banana.id][OwnerType.Group].add("xg")
        names.owners[banana.id][OwnerType.Location].add("xl")

        self.assertEqual(sum(names.count(r, OwnerType.User) for r in rows), 1)
        self.assertEqual(sum(names.count(r, OwnerType.Group) for r in rows), 2)
        self.assertEqual(sum(names.count(r, OwnerType.Location) for r in rows), 3)

        self.assertEqual(names.get_usernames(banana), [])
        self.assertEqual(names.get_group_names(banana), ['g2'])
        self.assertEqual(names.get_location_codes(banana), ['loc2'])

    def upload(self, rows, *, check_result=True, **kw):
        data = self.make_rows(rows)
        workbook = self.get_workbook_from_data(self.headers, data)
        result = _run_upload(self.domain, workbook, **kw)
        if check_result:
            self.check_upload_result(result)
        return result

    def prepare_download(self, table_tags):
        def sheet_dict(tag):
            headers = sheets[tag]["headers"]
            data = {
                "type": type_rows[tag],
                "rows": [dict(zip(headers, row)) for row in sheets[tag]["rows"]],
            }
            return data
        tables = LookupTable.objects.by_domain(self.domain)
        table_ids = [t.id.hex for t in tables if t.tag in table_tags]
        data_types, sheets = mod._prepare_fixture(table_ids, self.domain)
        type_headers = sheets["types"]["headers"]
        type_rows = {x["table_id"]: x for x in (
            dict(zip(type_headers, r)) for r in sheets["types"]["rows"]
        )}
        return {t.tag: sheet_dict(t.tag) for t in data_types}

    @staticmethod
    def get_workbook_from_data(headers, rows):
        file = BytesIO()
        export_raw(headers, rows, file, format=Format.XLS_2007)
        return get_workbook(file)

    def check_upload_result(self, result):
        self.assertFalse(result.errors)
        self.assertFalse(result.messages)

    headers = (
        ('types', ('Delete(Y/N)', 'table_id', 'is_global?', 'field 1')),
        ('things', ('UID', 'Delete(Y/N)', 'field: name', 'user 1', 'group 1', 'location 1')),
    )

    @staticmethod
    def make_rows(item_rows):
        return (
            ('types', [('N', 'things', 'no', 'name')]),
            ('things', item_rows),
        )


def test_get_indexed_field_numbers():
    table = create_index_tables()[1]
    eq(mod.get_indexed_field_numbers([table]), {0, 2, 4})


def test_get_indexed_field_numbers_for_multiple_tables():
    tables = create_index_tables()
    eq(mod.get_indexed_field_numbers(tables), {0, 1, 2, 4, 6})


def test_iter_types_headers():
    eq(list(mod.iter_types_headers(7, {0, 3, 6})), [
        "field 1",
        "field 1: is_indexed?",
        "field 2",
        "field 3",
        "field 4",
        "field 4: is_indexed?",
        "field 5",
        "field 6",
        "field 7",
        "field 7: is_indexed?",
    ])


def create_index_tables():
    return [
        LookupTable(fields=[
            TypeField(name="a1", is_indexed=True),
            TypeField(name="a2", is_indexed=True),
            TypeField(name="a3"),
        ]),
        LookupTable(fields=[
            TypeField(name="b1", is_indexed=True),
            TypeField(name="b2"),
            TypeField(name="b3", is_indexed=True),
            TypeField(name="b4"),
            TypeField(name="b5", is_indexed=True),
        ]),
        LookupTable(fields=[
            TypeField(name="c1"),
            TypeField(name="c2"),
            TypeField(name="c3"),
            TypeField(name="c4"),
            TypeField(name="c5"),
            TypeField(name="c6"),
            TypeField(name="c7", is_indexed=True),
        ]),
    ]
