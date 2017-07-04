from couchdbkit import ResourceNotFound
from dimagi.ext.couchdbkit import (
    BooleanProperty,
    Document,
    DocumentSchema,
    SchemaListProperty,
    StringProperty,
)
from corehq.apps.app_manager.models import Application
from corehq.apps.groups.models import Group
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.users.models import WebUser
from casexml.apps.phone.models import OTARestoreWebUser


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


class UserDataPermission(DocumentSchema):
    user_data_key = StringProperty()
    user_data_value = StringProperty()


class AppUserDataPermission(DocumentSchema):
    app_id = StringProperty()
    user_data_permissions = SchemaListProperty(UserDataPermission, default=[])

    def user_has_permission(self, user):
        return any(
            user.user_data.get(permission.user_data_key) == permission.user_data_value
            for permission in self.user_data_permissions
        )


class ApplicationAccess(Document):
    """
    This is used to control which users/groups can access which applications on cloudcare.
    """
    domain = StringProperty()
    app_groups = SchemaListProperty(AppGroup, default=[])
    app_userdata_permissions = SchemaListProperty(AppUserDataPermission, default=[])
    restrict = BooleanProperty(default=False)

    @classmethod
    def get_by_domain(cls, domain):
        from corehq.apps.cloudcare.dbaccessors import \
            get_application_access_for_domain
        self = get_application_access_for_domain(domain)
        return self or cls(domain=domain)

    def user_can_access_app(self, user, app):
        app_id = app['_id']
        app_ids = (app_id, app['copy_of'] or ())

        if not self.restrict or isinstance(user, (WebUser, OTARestoreWebUser)):
            return True

        return self.group_permitted(app_ids, user) or self.userdata_permitted(app_ids, user)

    def group_permitted(self, app_ids, user):
        app_group = None
        for app_group in self.app_groups:
            if app_group.app_id in app_ids:
                break
        if app_group:
            return Group.user_in_group(user.user_id, app_group.group_id)

    def userdata_permitted(self, app_ids, user):
        if isinstance(app_ids, basestring):
            app_ids = [app_ids]
        permissions = [
            userdata_permission for userdata_permission in self.app_userdata_permissions
            if userdata_permission.app_id in app_ids
        ]
        return any([permission.user_has_permission(user) for permission in permissions])

    @classmethod
    def get_template_json(cls, domain, apps):
        app_ids = {app['_id'] for app in apps}
        self = ApplicationAccess.get_by_domain(domain)
        j = self.to_json()

        app_group_apps = {
            app_group['app_id']: app_group
            for app_group in j['app_groups']
            if app_group['app_id'] in app_ids
        }
        userdata_apps = {
            userdata_app['app_id']: userdata_app
            for userdata_app in j['app_userdata_permissions']
            if userdata_app['app_id'] in app_ids
        }

        for app_id in app_ids:
            if app_id not in app_group_apps:
                app_group_apps[app_id] = {
                    'app_id': app_id,
                    'group_id': None,
                }
            if app_id not in userdata_apps:
                userdata_apps[app_id] = {
                    'app_id': app_id,
                    'user_data_permissions': []
                }
        j['app_groups'] = app_group_apps.values()
        j['app_userdata_permissions'] = userdata_apps.values()
        return j
