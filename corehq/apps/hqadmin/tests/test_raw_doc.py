import json

from django.test import TestCase

from corehq.apps.fixtures.models import Field, LookupTable, LookupTableRow, TypeField

from ..views.data import raw_doc_lookup


class TestRawDocLookup(TestCase):
    maxDiff = None

    def test_lookuptable_raw_doc(self):
        table = make_lookuptable()
        table.save()

        data = raw_doc_lookup(table.id.hex)
        actual_doc = json.loads(data["doc"])
        last_modified = actual_doc["fields"]["last_modified"]

        expected_doc = {
            "model": "fixtures.lookuptable",
            "pk": str(table.id),
            "fields": {
                "domain": "test-domain",
                "is_global": True,
                "is_synced": False,
                "tag": "item",
                "fields": [
                    {
                        "name": "qty",
                        "properties": [],
                        "is_indexed": False,
                    }
                ],
                "item_attributes": ["name"],
                'last_modified': last_modified,
                "description": "",
            },
        }

        self.assertEqual(actual_doc, expected_doc)
        results = {r.dbname: r.result for r in data["db_results"]}
        self.assertEqual(results["fixtures_lookuptable"], "found", results)

        data = raw_doc_lookup(str(table.id))
        self.assertEqual(json.loads(data["doc"]), expected_doc)

    def test_lookuptablerow_raw_doc(self):
        table = make_lookuptable()
        table.save()
        row = LookupTableRow(
            domain="test-domain",
            table=table,
            fields={"qty": [Field(value="2")]},
            item_attributes={"name": "iron"},
            sort_key=0,
        )
        row.save()

        data = raw_doc_lookup(row.id.hex)
        actual_doc = json.loads(data["doc"])
        last_modified = actual_doc["fields"]["last_modified"]

        expected_doc = {
            "model": "fixtures.lookuptablerow",
            "pk": str(row.id),
            "fields": {
                "table": str(table.id),
                "domain": "test-domain",
                "fields": {
                    "qty": [{"value": "2", "properties": {}}],
                },
                "item_attributes": {"name": "iron"},
                "last_modified": last_modified,
                "sort_key": 0,
            },
        }

        self.assertEqual(actual_doc, expected_doc)
        results = {r.dbname: r.result for r in data["db_results"]}
        self.assertEqual(results["fixtures_lookuptablerow"], "found", results)

        data = raw_doc_lookup(str(row.id))
        self.assertEqual(json.loads(data["doc"]), expected_doc)

    def test_raw_doc_with_invalid_uuid(self):
        data = raw_doc_lookup("abcxyz")
        self.assertNotIn("doc", data)
        self.assertEqual({r.result for r in data["db_results"]}, {"missing"})


def make_lookuptable():
    return LookupTable(
        domain='test-domain',
        is_global=True,
        tag='item',
        fields=[TypeField(name='qty')],
        item_attributes=['name'],
    )
