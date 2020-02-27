from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(self):
        return 'ApiUser'

    @classmethod
    def sql_class(self):
        from corehq.apps.api.models import ApiUser
        return ApiUser

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            id=doc['_id'],
            defaults={
                "password": doc.get("password"),
                "permissions": doc.get("permissions", []),
            })
        return (model, created)
