from couchdbkit import ResourceNotFound
from django.db import DEFAULT_DB_ALIAS, models
from memoized import memoized

from dimagi.ext.couchdbkit import (
    BooleanProperty,
    Document,
    DocumentSchema,
    SchemaListProperty,
    StringProperty,
)


from corehq.apps.app_manager.models import Application
from corehq.apps.cachehq.mixins import QuickCachedDocumentMixin
from corehq.apps.groups.models import Group


class ApplicationAccess(models.Model):
     domain = models.CharField(max_length=255, null=False, unique=True)
    restrict = models.BooleanField(default=False)

    def save(self, force_insert=False, force_update=False, using=DEFAULT_DB_ALIAS, update_fields=None):
        from corehq.apps.cloudcare.dbaccessors import get_application_access_for_domain
        get_application_access_for_domain.clear(self.domain)
        super().save(
            force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields
        )

    def user_can_access_app(self, user, app):
        user_id = user['_id']
        app_id = app['_id']
        if not self.restrict or user['doc_type'] == 'WebUser':
            return True
        app_group = None
        for app_group in self.sqlappgroup_set.all():
            if app_group.app_id in (app_id, app['copy_of'] or ()):
                break
        if app_group:
            return Group.user_in_group(user_id, app_group.group_id)
        else:
            return False

    def get_template_json(self, apps):
        apps_by_id = {a.get_id: a for a in apps}

        # Filter self's apps down to those given
        group_id_by_app_id = {
            app_group.app_id: app_group.group_id
            for app_group in self.sqlappgroup_set.all()
            if app_group.app_id in apps_by_id.keys()
        }

        # Add any apps passed in that aren't known to self
        for app_id in apps_by_id.keys():
            if app_id not in group_id_by_app_id:
                group_id_by_app_id[app_id] = None

        return {
            'domain': self.domain,
            'restrict': self.restrict,
            'app_groups': sorted([
                {
                    'app_id': app_id,
                    'group_id': group_id,
                } for app_id, group_id in group_id_by_app_id.items()
            ], key=lambda app_group: apps_by_id[app_group['app_id']].name),
        }


class SQLAppGroup(models.Model):
    app_id = models.CharField(max_length=255)
    group_id = models.CharField(max_length=255, null=True)
    application_access = models.ForeignKey('ApplicationAccess', on_delete=models.CASCADE)

    class Meta(object):
        unique_together = ('app_id', 'group_id')
