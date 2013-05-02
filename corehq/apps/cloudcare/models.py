from couchdbkit import ResourceNotFound, BooleanProperty
from couchdbkit.ext.django.schema import Document, SchemaListProperty, DictProperty, StringProperty, DocumentSchema, Property
from django.core.cache import cache
from corehq.apps.app_manager.models import Application
from corehq.apps.groups.models import Group
from dimagi.utils.decorators.memoized import memoized

class SelectChoice(DocumentSchema):
    label = DictProperty()
    stringValue = StringProperty()
    value = Property()

class CasePropertySpec(DocumentSchema):
    key = StringProperty()
    label = DictProperty()
    type = StringProperty(choices=['string', 'select', 'date', 'group'], default='string')
    choices = SchemaListProperty(SelectChoice)

class CaseSpec(Document):
    name = StringProperty()
    domain = StringProperty()
    case_type = StringProperty()
    propertySpecs = SchemaListProperty(CasePropertySpec)

    @classmethod
    def get_suggested(cls, domain, case_type=None):
        key = [domain]
        if case_type:
            key.append(case_type)
        return cls.view('cloudcare/case_specs_by_domain_case_type',
            reduce=False,
            include_docs=True,
            startkey=key,
            endkey=key + [{}],
        )

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

    @memoized
    def get_collated(self):
        cache_key = 'get_collated-%s-%s' % (self.app_id, self.group_id)
        r = cache.get(cache_key)
        if not r:
            r = {
                'app': self.app_stub,
                'group': self.group_stub,
                }
            cache.set(cache_key, r, 15*60)
        return r


class ApplicationAccess(Document):
    domain = StringProperty()
    app_groups = SchemaListProperty(AppGroup, default=[])
    restrict = BooleanProperty(default=False)

    @classmethod
    def get_by_domain(cls, domain):
        self = cls.view('cloudcare/application_access',
            key=domain,
            include_docs=True
        ).first()
        return self or cls(domain=domain)

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