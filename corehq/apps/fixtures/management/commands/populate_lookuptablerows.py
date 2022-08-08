from uuid import UUID
from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand

from ...models import Field


class Command(PopulateSQLCommand):

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
        return "TODO: add once the PR adding this file is merged"

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
                couch.get("item_attributes") or {},
                sql.item_attributes,
            ),
            cls.diff_value(
                "sort_key",
                couch.get("sort_key") or 0,
                sql.sort_key,
            ),
        ]
        return diffs

    def update_or_create_sql_object(self, doc):
        if not self.data_type_exists(doc["data_type_id"]):
            return None, False
        return self.sql_class().objects.update_or_create(
            id=UUID(doc['_id']),
            defaults={
                "domain": doc["domain"],
                "table_id": UUID(doc["data_type_id"]),
                "fields": couch_to_sql_fields(doc["fields"]),
                "item_attributes": doc.get("item_attributes") or {},
                "sort_key": doc.get("sort_key") or 0,
            },
        )

    def data_type_exists(self, data_type_id):
        try:
            return self.data_type_existence[data_type_id]
        except KeyError:
            exists = self.couch_db().doc_exist(data_type_id)
            self.data_type_existence[data_type_id] = exists
            return exists


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
