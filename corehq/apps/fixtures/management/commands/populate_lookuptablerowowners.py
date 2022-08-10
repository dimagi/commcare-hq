from uuid import UUID

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand
from ...models import OwnerType


class Command(PopulateSQLCommand):

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.data_item_existence = {}

    @classmethod
    def couch_db_slug(cls):
        return "fixtures"

    @classmethod
    def couch_doc_type(self):
        return 'FixtureOwnership'

    @classmethod
    def sql_class(self):
        from corehq.apps.fixtures.models import LookupTableRowOwner
        return LookupTableRowOwner

    @classmethod
    def commit_adding_migration(cls):
        return "TODO: add once the PR adding this file is merged"

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        """
        This should compare each attribute of the given couch document and sql object.
        Return a list of human-reaedable strings describing their differences, or None if the
        two are equivalent. The list may contain `None` or empty strings which will be filtered
        out before display.

        Note: `diff_value`, `diff_attr` and `diff_lists` methods of `PopulateSQLCommand` are useful
        helpers.
        """
        fields = ["domain", "owner_id"]
        diffs = [cls.diff_attr(name, couch, sql) for name in fields]
        diffs.append(cls.diff_value(
            "owner_type",
            OwnerType.from_string(couch["owner_type"]),
            sql.owner_type,
        ))
        diffs.append(cls.diff_value(
            "row_id",
            UUID(couch["data_item_id"]),
            sql.row_id,
        ))
        return diffs

    def update_or_create_sql_object(self, doc):
        if not self.data_item_exists(doc["data_item_id"]):
            return None, False
        model, created = self.sql_class().objects.update_or_create(
            couch_id=doc['_id'],
            defaults={
                "domain": doc["domain"],
                "row_id": UUID(doc["data_item_id"]),
                "owner_type": OwnerType.from_string(doc["owner_type"]),
                "owner_id": doc.get("owner_id"),
            })
        return model, created

    def data_item_exists(self, data_type_id):
        try:
            return self.data_item_existence[data_type_id]
        except KeyError:
            exists = self.couch_db().doc_exist(data_type_id)
            self.data_item_existence[data_type_id] = exists
            return exists
