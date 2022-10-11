from decimal import Decimal
from uuid import UUID

from .base import PopulateLookupTableCommand
from ...models import Field


class Command(PopulateLookupTableCommand):

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.data_type_existence = {}

    @classmethod
    def couch_db_slug(cls):
        return "fixtures"

    @classmethod
    def couch_doc_type(cls):
        return 'FixtureDataItem'

    @classmethod
    def sql_class(cls):
        from ...models import LookupTableRow
        return LookupTableRow

    @classmethod
    def commit_adding_migration(cls):
        return "f829719365bca901f399bce0c543aeaa827fd630"

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        """
        Compare each attribute of the given couch document and sql
        object. Return a list of human-readable strings describing their
        differences, or None if the two are equivalent. The list may
        contain `None` or empty strings.
        """
        diffs = [
            cls.diff_attr("domain", couch, sql),
            cls.diff_value(
                "table_id",
                UUID(couch["data_type_id"]),
                sql.table_id,
            ),
            cls.diff_value(
                "fields",
                couch_to_sql_fields(couch["fields"]),
                sql.fields,
            ),
            cls.diff_value(
                "item_attributes",
                transform_item_attributes(couch.get("item_attributes") or {}),
                sql.item_attributes,
            ),
            cls.diff_value(
                "sort_key",
                couch.get("sort_key") or 0,
                sql.sort_key,
            ),
        ]
        return diffs

    def get_ids_to_ignore(self, docs):
        existence_map = self.data_type_existence
        data_type_ids = {d["data_type_id"] for d in docs}
        new_ids = data_type_ids - existence_map.keys()
        if new_ids:
            items = self.couch_db().view("_all_docs", keys=list(new_ids), reduce=False)
            existing_ids = {i["id"] for i in items if not (i.get("error") or i["value"].get("deleted"))}
            for data_type_id in new_ids:
                existence_map[data_type_id] = data_type_id in existing_ids
        return {d["_id"] for d in docs if not existence_map[d["data_type_id"]]}


def couch_to_sql_fields(data):
    def get_values(field):
        if isinstance(field, dict):
            return field["field_list"]
        # pre-2014 fields format
        assert isinstance(field, (str, int, float, type(None))), field
        return [{"field_value": str(field), "properties": {}}]
    return {
        name: [
            Field(val["field_value"], val["properties"])
            for val in get_values(field)
        ]
        for name, field in data.items()
    }


def transform_item_attributes(data):
    def convert(value):
        if isinstance(value, Decimal):
            return str(value)
        return value
    return {name: convert(value) for name, value in data.items()}
