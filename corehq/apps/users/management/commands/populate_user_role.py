from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand
from corehq.apps.users.models import UserRole
from corehq.apps.users.models_sql import migrate_role_assignable_by_to_sql, migrate_role_permissions_to_sql


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
            })
        couch_role = UserRole.wrap(doc)
        if couch_role.upstream_id:
            try:
                upstream_role = self.sql_class().objects.by_couch_id(couch_role.upstream_id)
            except self.sql_class().DoesNotExist:
                # if the upstream role is not yet in SQL create it now
                upstream_role = UserRole.get(couch_role.upstream_id)._migration_do_sync()
            model.upstream_id = upstream_role.id
        else:
            model.upstream_id = None
        migrate_role_permissions_to_sql(couch_role, model)
        migrate_role_assignable_by_to_sql(couch_role, model)
        return model, created
