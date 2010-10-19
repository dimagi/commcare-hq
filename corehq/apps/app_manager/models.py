from couchdbkit.ext.django.schema import *
from django.core.urlresolvers import reverse
from corehq.util import bitly
from corehq.util.webutils import URL_BASE

class XForm(Document):
    display_name = StringProperty()
    xmlns = StringProperty()
    submit_time = DateTimeProperty()
    domain = StringProperty()

class XFormGroup(Document):
    "Aggregate of all XForms with the same xmlns"
    display_name = StringProperty()
    xmlns = StringProperty()

class VersionedDoc(Document):
    domain = StringProperty()
    copy_of = StringProperty()
    version = IntegerProperty()
    short_url = StringProperty()
    def save(self, **params):
        self.version = self.version + 1 if self.version else 1
        super(VersionedDoc, self).save()
        if not self.short_url:
            self.short_url = bitly.shorten(
                URL_BASE + reverse('corehq.apps.app_manager.views.download_jad', args=[self.domain, self._id])
            )
            super(VersionedDoc, self).save()

class Application(VersionedDoc):
    modules = ListProperty()
    trans = DictProperty()
    name = DictProperty()
    langs = ListProperty()
    def get_modules(self):
        for i in range(len(self.modules)):
            yield Module(self, i)
    def get_module(self, i):
        return Module(self, i)
    @property
    def id(self):
        return self._id
    def get_absolute_url(self):
        return reverse('corehq.apps.app_manager.views.app_view', args=[self.domain,  self.id])

class RemoteApp(VersionedDoc):
    profile_url = StringProperty()
    suite_url = StringProperty()
    name = DictProperty()

    @classmethod
    def get_app(cls, domain, app_id):
        # raise error if domain doesn't exist
        Domain.objects.get(name=domain)
        app = RemoteApp.get(app_id)
        if app.domain != domain:
            raise Exception("App %s not in domain %s" % (app_id, domain))
        return app

    @property
    def id(self):
        return self._id

    def get_absolute_url(self):
        return reverse('corehq.apps.remote_apps.views.app_view', args=[self.domain, self.id])




# The following classes are wrappers for the subparts of an application document
class DictWrapper(object):
    def __eq__(self, other):
        try:
            return (self.id == other.id) and (self.parent == other.parent)
        except:
            return False
def _call_dict(fn):
    def _fn(self, *args, **kwargs):
        return getattr(self._dict, fn)(*args, **kwargs)
    return _fn

for fn in ('__getitem__', '__setitem__', '__contains__', 'update', 'get'):
    setattr(DictWrapper, fn, _call_dict(fn))

class Module(DictWrapper):
    def __init__(self, app, id):
        self.app = app
        self.parent = self.app
        self.id = int(id)
        self._dict = app.modules[self.id]

    def get_forms(self):
        for i in range(len(self['forms'])):
            yield Form(self, i)
    def get_form(self, i):
        return Form(self, i)

class Form(DictWrapper):
    def __init__(self, module, id):
        self.module = module
        self.parent = self.module
        self.id = int(id)
        self._dict = module['forms'][self.id]

class Domain(object):
    def __init__(self, name):
        self.name = name
    def get_app(self, app_id):
        app = Application.get(app_id)
        if app.doc_type != "Application":
            app = RemoteApp.get(app_id)
        assert(app.domain == self.name)
        return app