from django.conf import settings

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand
from corehq.apps.users.models import UserRole, Permissions
from corehq.apps.users.models_sql import (
    migrate_role_assignable_by_to_sql,
    migrate_role_permissions_to_sql,
)


class Command(PopulateSQLCommand):
    @classmethod
    def couch_db_slug(cls):
        return settings.USERS_GROUPS_DB

    @classmethod
    def couch_doc_type(self):
        return 'UserRole'

    @classmethod
    def sql_class(self):
        from corehq.apps.users.models import SQLUserRole
        return SQLUserRole

    @classmethod
    def commit_adding_migration(cls):
        return "4f5a5ef0a9b5ef9873a9b2dce5646d7aa881c416"

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        diffs = []
        for field in UserRole._migration_get_fields():
            diffs.append(cls.diff_attr(field, couch, sql))

        couch_permissions = {
            info.name: info
            for info in Permissions.wrap(couch.get("permissions", {})).to_list()
        }
        sql_permissions = {
            info.name: info
            for info in sql.permissions.to_list()
        }

        for name in sorted(set(couch_permissions) | set(sql_permissions)):
            couch_permission = couch_permissions.get(name)
            diffs.append(cls.diff_attr(
                "allow",
                couch_permission._asdict() if couch_permission else {},
                sql_permissions.get(name),
                name_prefix=f"permissions.{name}"
            ))

        couch_assignable_by = couch.get("assignable_by")
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
                "upstream_id": doc.get("upstream_id"),
            })
        couch_role = UserRole.wrap(doc)
        migrate_role_permissions_to_sql(couch_role, model)
        migrate_role_assignable_by_to_sql(couch_role, model)
        return model, created
