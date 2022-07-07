from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand

from ...models import TypeField


class Command(PopulateSQLCommand):

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
        return "TODO: add once the PR adding this file is merged"

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        """
        Compare each attribute of the given couch document and sql
        object. Return a list of human-readable strings describing their
        differences, or None if the two are equivalent. The list may
        contain `None` or empty strings.
        """
        fields = ["domain", "is_global", "tag", "item_attributes"]
        diffs = [cls.diff_attr(name, couch, sql) for name in fields]
        if couch.get("description") or sql.description:
            diffs.append(cls.diff_value(
                "description",
                couch.get("description"),
                sql.description,
            ))
        diffs.append(cls.diff_value(
            "fields",
            [transform_field(f) for f in couch["fields"]],
            sql.fields,
        ))
        return diffs

    def update_or_create_sql_object(self, doc):
        return self.sql_class().objects.update_or_create(
            id=doc['_id'],
            defaults={
                "domain": doc["domain"],
                "is_global": doc.get("is_global", False),
                "tag": doc["tag"],
                "fields": [transform_field(f) for f in doc.get("fields", [])],
                "item_attributes": doc.get("item_attributes", []),
                "description": doc.get("description") or ""
            },
        )


def transform_field(data):
    copy = data.copy()
    copy.pop("doc_type")
    return TypeField(name=copy.pop("field_name"), **copy)
