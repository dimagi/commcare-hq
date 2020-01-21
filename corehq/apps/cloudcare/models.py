from couchdbkit import ResourceNotFound
from django.db import models, transaction
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


class SQLApplicationAccess(models.Model):
    domain = models.CharField(max_length=255, null=False, unique=True)
    restrict = models.BooleanField(default=False)


class SQLAppGroup(models.Model):
    app_id = models.CharField(max_length=255, null=False)
    group_id = models.CharField(max_length=255)
    application_access = models.ForeignKey('SQLApplicationAccess', on_delete=models.CASCADE)

    class Meta(object):
        unique_together = ('app_id', 'group_id')


class AppGroup(DocumentSchema):
    app_id = StringProperty()
    group_id = StringProperty()

    @property
    @memoized
    def group(self):
        try:
            group = Group.get(self.group_id)
            assert group.doc_type is 'Group'
            return group
        except (ResourceNotFound, AssertionError):
            return None

    @property
    @memoized
    def group_stub(self):
        return {
            'name': self.group.name,
            '_id': self.group.get_id,
            }

    @property
    @memoized
    def app(self):
        try:
            app = Application.get(self.app_id)
            assert app.doc_type is 'Application'
            return app
        except (ResourceNotFound, AssertionError):
            return None

    @property
    @memoized
    def app_stub(self):
        return {
            'name': self.app.name,
            '_id': self.app.get_id,
            }


class ApplicationAccess(QuickCachedDocumentMixin, Document):
    """
    This is used to control which users/groups can access which applications on cloudcare.
    """
    domain = StringProperty()
    app_groups = SchemaListProperty(AppGroup, default=[])
    restrict = BooleanProperty(default=False)

    @classmethod
    def get_by_domain(cls, domain):
        from corehq.apps.cloudcare.dbaccessors import get_application_access_for_domain
        self = get_application_access_for_domain(domain)
        return self or cls(domain=domain)

    def clear_caches(self):
        from corehq.apps.cloudcare.dbaccessors import get_application_access_for_domain
        get_application_access_for_domain.clear(self.domain)
        super(ApplicationAccess, self).clear_caches()

    def user_can_access_app(self, user, app):
        user_id = user['_id']
        app_id = app['_id']
        if not self.restrict or user['doc_type'] == 'WebUser':
            return True
        app_group = None
        for app_group in self.app_groups:
            if app_group.app_id in (app_id, app['copy_of'] or ()):
                break
        if app_group:
            return Group.user_in_group(user_id, app_group.group_id)
        else:
            return False

    @classmethod
    def get_template_json(cls, domain, apps):
        app_ids = dict([(app['_id'], app) for app in apps])
        self = ApplicationAccess.get_by_domain(domain)
        j = self.to_json()
        merged_access_list = []
        for a in j['app_groups']:
            app_id = a['app_id']
            if app_id in app_ids:
                merged_access_list.append(a)
                del app_ids[app_id]
        for app in app_ids.values():
            merged_access_list.append({
                'app_id': app['_id'],
                'group_id': None
            })
        j['app_groups'] = merged_access_list
        return j

    def save(self, *args, **kwargs):
        # Save to SQL
        with transaction.atomic():
            model, created = SQLApplicationAccess.objects.update_or_create(
                domain=self.domain,
                defaults={
                    'restrict': self.restrict,
                }
            )
            model.sqlappgroup_set.set([
                SQLAppGroup.objects.update_or_create(app_id=group.app_id, defaults={'group_id': group.group_id})[0]
                for group in self.app_groups
            ], bulk=False)
            model.save()

        # Save to couch
        super().save(*args, **kwargs)
