from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


class Command(PopulateSQLCommand):
    @classmethod
    def couch_db_slug(cls):
        return "users"

    @classmethod
    def couch_doc_type(self):
        return 'UserRole'

    @classmethod
    def sql_class(self):
        from corehq.apps.users.models import SQLUserRole
        return SQLUserRole

    @classmethod
    def commit_adding_migration(cls):
        return "TODO: add once the PR adding this file is merged"

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            couch_id=doc['_id'],
            defaults={
                "domain": doc.get("domain"),
                "name": doc.get("name"),
                "default_landing_page": doc.get("default_landing_page"),
                "is_non_admin_editable": doc.get("is_non_admin_editable"),
                "is_archived": doc.get("is_archived"),
                "upstream_id": doc.get("upstream_id"),
                "original_doc": doc.get("original_doc"),
            })
        return model, created
