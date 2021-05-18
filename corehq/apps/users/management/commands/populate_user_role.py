from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand
from corehq.apps.users.models import UserRole, Permissions
from corehq.apps.users.models_sql import (
    migrate_role_assignable_by_to_sql,
    migrate_role_permissions_to_sql,
    SQLUserRole,
)


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

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        diffs = []
        for field in UserRole._migration_get_fields():
            diffs.append(cls.diff_attr(field, couch, sql))

        couch_upstream_id = couch.get("upstream_id", None)
        sql_upstream_id = sql.upstream_id
        if couch_upstream_id or sql_upstream_id:
            try:
                sql_mapped_upstream_id = SQLUserRole.objects.get(id=sql_upstream_id).couch_id
            except SQLUserRole.DoesNotExist:
                sql_mapped_upstream_id = None
            diffs.append(cls.diff_value("upstream_id", couch_upstream_id, sql_mapped_upstream_id))

        couch_permissions = {
            info.name: info
            for info in Permissions.wrap(couch["permissions"]).to_list()
        }
        sql_permissions = {
            info.name: info
            for info in sql.permissions.to_list()
        }

        for name in sorted(set(couch_permissions) | set(sql_permissions)):
            couch_permission = couch_permissions.get(name)
            diffs.append(cls.diff_attr(
                "allow",
                couch_permission._asdict() if couch_permission else None,
                sql_permissions.get(name),
                name_prefix=f"permissions.{name}"
            ))

        couch_assignable_by = couch["assignable_by"]
        sql_assignable_by = list(sql.roleassignableby_set.values_list('assignable_by_role__couch_id', flat=True))
        diffs.extend(cls.diff_lists(
            "assignable_by",
            sorted(couch_assignable_by) if couch_assignable_by else [],
            sorted(sql_assignable_by),
        ))
        return diffs

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
