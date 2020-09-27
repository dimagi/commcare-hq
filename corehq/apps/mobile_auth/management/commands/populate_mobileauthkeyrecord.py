from dimagi.utils.parsing import string_to_utc_datetime

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(self):
        return 'MobileAuthKeyRecord'

    @classmethod
    def sql_class(self):
        from corehq.apps.mobile_auth.models import SQLMobileAuthKeyRecord
        return SQLMobileAuthKeyRecord

    @classmethod
    def commit_adding_migration(cls):
        return "TODO"

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        diffs = []
        for attr in ["domain", "user_id", "type", "key"]:
            diffs.append(cls.diff_attr(attr, couch, sql))
        for attr in ["valid", "expires"]:
            diffs.append(cls.diff_attr(attr, couch, sql, wrap=string_to_utc_datetime))
        diffs = [d for d in diffs if d]
        return "\n".join(diffs) if diffs else None

    def update_or_create_sql_object(self, doc):
        # Use get_or_create so that if sql model exists we don't bother saving it,
        # since these models are read-only
        model, created = self.sql_class().objects.update_or_create(
            id=doc['_id'],
            defaults={
                "domain": doc.get("domain"),
                "user_id": doc.get("user_id"),
                "valid": string_to_utc_datetime(doc.get("valid")),
                "expires": string_to_utc_datetime(doc.get("expires")),
                "type": doc.get("type"),
                "key": doc.get("key"),
            })
        return (model, created)
