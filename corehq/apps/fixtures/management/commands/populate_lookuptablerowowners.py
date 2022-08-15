from uuid import UUID

from couchdbkit import ResourceNotFound

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

    def should_ignore(self, doc):
        data_item_id = doc["data_item_id"]
        try:
            exists = self.data_item_existence[data_item_id]
        except KeyError:
            try:
                data_type_id = self.couch_db().get(data_item_id)["data_type_id"]
            except ResourceNotFound:
                exists = False
            else:
                exists = self.couch_db().doc_exist(data_type_id)
            self.data_item_existence[data_item_id] = exists
        return not exists
