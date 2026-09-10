from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from corehq.apps.app_manager import lookup_table_import
from corehq.apps.app_manager.lookup_table_import import (
    _destination_tag,
    _get_referenced_lookup_table_tags,
    copy_lookup_tables,
    delete_copied_lookup_tables,
    rewrite_lookup_table_references,
)
from corehq.apps.fixtures.constants import LOOKUP_TABLE_TAG_MAX_LENGTH
from corehq.apps.fixtures.models import (
    Field,
    LookupTable,
    LookupTableRow,
    LookupTableRowOwner,
    OwnerType,
    TypeField,
)


class TestLookupTableReferenceHandling(SimpleTestCase):
    def test_finds_structured_xml_and_unicode_references(self):
        app_doc = {
            "modules": [{"fixture_select": {"fixture_type": "district"}}],
            "forms": ["instance('item-list:província')/província_list/província"],
        }

        assert _get_referenced_lookup_table_tags(app_doc) == {"district", "província"}

    def test_rewrites_exact_references_and_fixture_paths(self):
        app_doc = {
            "fixture_type": "fruit",
            "form": (
                "instance('item-list:fruit')/fruit_list/fruit "
                "instance('item-list:fruit-basket')/fruit-basket_list/fruit-basket"
            ),
        }

        rewrite_lookup_table_references(app_doc, {"fruit": "fruit-1"})

        assert app_doc["fixture_type"] == "fruit-1"
        assert "item-list:fruit-1')/fruit-1_list/fruit-1" in app_doc["form"]
        assert "item-list:fruit-basket')/fruit-basket_list/fruit-basket" in app_doc["form"]

    def test_destination_tag_stays_within_limit(self):
        source_tag = "a" * LOOKUP_TABLE_TAG_MAX_LENGTH

        assert _destination_tag(source_tag, 12) == f"{'a' * 28}-12"

class TestCopyLookupTables(TestCase):
    source_domain = "lookup-table-import-source"
    destination_domain = "lookup-table-import-destination"

    def setUp(self):
        self.source_table = LookupTable.objects.create(
            domain=self.source_domain,
            tag="fruit",
            fields=[TypeField("name", ["lang"], True)],
            item_attributes=["color"],
            description="Fruit table",
            is_global=False,
            is_synced=True,
        )
        self.source_row = LookupTableRow.objects.create(
            domain=self.source_domain,
            table=self.source_table,
            fields={"name": [Field("Apple", {"lang": "en"})]},
            item_attributes={"color": "red"},
            sort_key=0,
        )
        LookupTableRowOwner.objects.create(
            domain=self.source_domain,
            row=self.source_row,
            owner_type=OwnerType.User,
            owner_id="user-id",
        )

    def test_copies_schema_rows_without_ownership(self):
        result = copy_lookup_tables(
            {"source": "instance('item-list:fruit')/fruit_list/fruit"},
            self.source_domain,
            self.destination_domain,
        )

        copied_table = LookupTable.objects.get(domain=self.destination_domain, tag="fruit")
        copied_row = LookupTableRow.objects.get(table=copied_table)
        assert copied_table.fields == self.source_table.fields
        assert copied_table.item_attributes == ["color"]
        assert copied_table.description == "Fruit table"
        assert copied_table.is_global
        assert not copied_table.is_synced
        assert copied_row.fields == self.source_row.fields
        assert copied_row.item_attributes == {"color": "red"}
        assert not LookupTableRowOwner.objects.filter(row=copied_row).exists()
        assert result.tag_mapping == {"fruit": "fruit"}
        assert result.missing_tags == ()

    def test_uses_next_available_suffix(self):
        LookupTable.objects.create(domain=self.destination_domain, tag="fruit")
        LookupTable.objects.create(domain=self.destination_domain, tag="fruit-1")

        result = copy_lookup_tables(
            {"fixture_type": "fruit"},
            self.source_domain,
            self.destination_domain,
        )

        assert result.tag_mapping == {"fruit": "fruit-2"}

    def test_reports_missing_and_does_not_copy_unreferenced_tables(self):
        result = copy_lookup_tables(
            {"source": "instance('item-list:missing')"},
            self.source_domain,
            self.destination_domain,
        )

        assert result.tag_mapping == {}
        assert result.missing_tags == ("missing",)
        assert not LookupTable.objects.filter(domain=self.destination_domain).exists()

    def test_cleanup_only_deletes_tables_created_by_import(self):
        existing = LookupTable.objects.create(domain=self.destination_domain, tag="existing")
        result = copy_lookup_tables(
            {"fixture_type": "fruit"},
            self.source_domain,
            self.destination_domain,
        )

        delete_copied_lookup_tables(self.destination_domain, result.created_table_ids)

        assert LookupTable.objects.filter(id=existing.id).exists()
        assert not LookupTable.objects.filter(id__in=result.created_table_ids).exists()

    def test_keeps_successful_tables_when_one_copy_fails(self):
        LookupTable.objects.create(domain=self.source_domain, tag="vegetable")
        copy_table = lookup_table_import._copy_lookup_table

        def fail_on_vegetable(source_table, destination_domain):
            if source_table.tag == "vegetable":
                raise RuntimeError
            return copy_table(source_table, destination_domain)

        app_doc = {
            "fruit": "instance('item-list:fruit')",
            "vegetable": "instance('item-list:vegetable')",
        }
        with patch.object(lookup_table_import, "_copy_lookup_table", side_effect=fail_on_vegetable):
            result = copy_lookup_tables(app_doc, self.source_domain, self.destination_domain)

        assert result.tag_mapping == {"fruit": "fruit"}
        assert result.failed_tags == ("vegetable",)
        assert LookupTable.objects.filter(domain=self.destination_domain, tag="fruit").exists()
        assert not LookupTable.objects.filter(domain=self.destination_domain, tag="vegetable").exists()
