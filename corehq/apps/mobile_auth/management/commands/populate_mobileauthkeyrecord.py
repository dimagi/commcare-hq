from dimagi.utils.dates import force_to_datetime

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

    def update_or_create_sql_object(self, doc):
        # Use get_or_create so that if sql model exists we don't bother saving it,
        # since these models are read-only
        model, created = self.sql_class().objects.get_or_create(
            id=doc['_id'],
            defaults={
                "domain": doc.get("domain"),
                "user_id": doc.get("user_id"),
                "valid": force_to_datetime(doc.get("valid")),
                "expires": force_to_datetime(doc.get("expires")),
                "type": doc.get("type"),
                "key": doc.get("key"),
            })
        return (model, created)
