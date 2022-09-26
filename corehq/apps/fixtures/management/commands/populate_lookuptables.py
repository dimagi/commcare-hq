from django.db import transaction

from .base import PopulateLookupTableCommand
from ...models import FixtureDataType, LookupTable, TypeField


class Command(PopulateLookupTableCommand):

    @classmethod
    def couch_db_slug(cls):
        return "fixtures"

    @classmethod
    def couch_doc_type(cls):
        return 'FixtureDataType'

    @classmethod
    def sql_class(cls):
        from ...models import LookupTable
        return LookupTable

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
        diffs = [cls.diff_attr(name, couch, sql) for name in ["domain", "tag"]]
        diffs.append(cls.diff_value(
            "is_global",
            couch.get("is_global") or False,
            sql.is_global,
        ))
        for field in ["item_attributes", "description"]:
            diffs.append(cls.diff_maybe_empty_field(field, couch, sql))
        diffs.append(cls.diff_value(
            "fields",
            [transform_field(f) for f in couch["fields"]],
            sql.fields,
        ))
        return diffs

    @classmethod
    def diff_maybe_empty_field(cls, field, couch, sql):
        if couch.get(field) or getattr(sql, field):
            return cls.diff_value(field, couch.get(field), getattr(sql, field))

    def _migrate_docs(self, docs, logfile, fixup_diffs):
        super()._migrate_docs(docs, logfile, fixup_diffs)
        if fixup_diffs:
            self.find_and_fix_duplicates(docs, logfile)

    def find_and_fix_duplicates(self, docs, logfile):
        sql_class = self.sql_class()
        couch_class = sql_class._migration_get_couch_model_class()
        assert sql_class is LookupTable, sql_class
        assert couch_class is FixtureDataType, couch_class

        couch_by_id = {d["_id"]: d for d in docs}
        sql_ids = {id.hex for id in LookupTable.objects
            .filter(id__in=list(couch_by_id))
            .values_list("id", flat=True)}
        seen = set()
        for missing_in_sql in couch_by_id.keys() - sql_ids:
            if missing_in_sql in seen:
                continue
            doc = couch_by_id[missing_in_sql]
            domain = doc["domain"]
            tag = doc["tag"]
            couch_docs = list(FixtureDataType.by_domain_tag(domain, tag))
            if len(couch_docs) == 1:
                delete_orphaned_sql_row(couch_docs[0], logfile)
            elif len(couch_docs) > 1:
                delete_duplicate_couch_docs(couch_docs, logfile)
            seen.update(doc._id for doc in couch_docs)


def delete_orphaned_sql_row(doc, logfile):
    with transaction.atomic():
        try:
            table = LookupTable.objects.get(domain=doc.domain, tag=doc.tag)
        except LookupTable.DoesNotExist:
            print("Unexpected: Orphaned SQL row not found:", doc._id, file=logfile)
            return
        if table._migration_couch_id == doc._id:
            print("Unexpected: SQL row is not orphaned:", doc._id, file=logfile)
            return
        LookupTable.objects.filter(id=table.id).delete()
        doc._migration_do_sync()
    print("Removed orphaned LookupTable row:", table.id, file=logfile)
    print(f"Recreated model for {type(doc).__name__} with id {doc._id}", file=logfile)


def delete_duplicate_couch_docs(couch_docs, logfile):
    pairs = {(d.domain, d.tag) for d in couch_docs}
    assert len(pairs) == 1, pairs
    (domain, tag), = pairs
    try:
        obj = LookupTable.objects.get(domain=domain, tag=tag)
    except LookupTable.DoesNotExist:
        print(f"Unexpected: SQL row not found: domain={domain} tag={tag}", file=logfile)
        return
    keep_id = obj._migration_couch_id
    couch_ids = sorted({d._id for d in couch_docs})
    assert len(couch_ids) > 1, couch_ids
    if couch_ids[0] != keep_id:
        print("Unexpected: SQL row does not have lowest id value:", keep_id, couch_ids, file=logfile)
        return
    # Rationale for removing all but the doc with the lowest id value:
    # That one would appear last in a restore payload, and is therefore
    # the one of most consequence on a mobile device.
    FixtureDataType.bulk_delete([d for d in couch_docs if d._id != keep_id])
    print("Removed duplicate FixtureDataTypes:", couch_ids[1:], file=logfile)


def transform_field(data):
    if isinstance(data, str):
        return TypeField(name=data)
    copy = data.copy()
    copy.pop("doc_type")
    return TypeField(name=copy.pop("field_name"), **copy)
