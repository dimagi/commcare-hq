from uuid import UUID

from .base import PopulateLookupTableCommand
from ...models import OwnerType


class Command(PopulateLookupTableCommand):

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
        return "f829719365bca901f399bce0c543aeaa827fd630"

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

    def get_ids_to_ignore(self, docs):
        existence_map = self.data_item_existence
        data_item_ids = {d["data_item_id"] for d in docs}
        new_ids = data_item_ids - existence_map.keys()
        if new_ids:
            results = self.couch_db().view(
                "_all_docs", keys=list(new_ids), include_docs=True, reduce=False)
            items = (r["doc"] for r in results if r.get("doc"))
            item_type_map = {i["_id"]: i["data_type_id"] for i in items}
            type_ids = set(item_type_map.values())
            types = self.couch_db().view("_all_docs", keys=list(type_ids), reduce=False)
            existing_type_ids = {t["id"] for t in types if not (t.get("error") or t["value"].get("deleted"))}
            NOMATCH = object()
            for data_item_id in new_ids:
                existence_map[data_item_id] = \
                    item_type_map.get(data_item_id, NOMATCH) in existing_type_ids
        return {d["_id"] for d in docs if not existence_map[d["data_item_id"]]}
