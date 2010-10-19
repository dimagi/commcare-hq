from django.db import models
from couchdbkit.ext.django.schema import *
from django.core.urlresolvers import reverse

class XForm(Document):
    display_name = StringProperty()
    xmlns = StringProperty()
    submit_time = DateTimeProperty()
    domain = StringProperty()

class XFormGroup(Document):
    "Aggregate of all XForms with the same xmlns"
    display_name = StringProperty()
    xmlns = StringProperty()

class Application(Document):
    domain = StringProperty()
    modules = ListProperty()
    trans = DictProperty()
    langs = ListProperty()
    copy_of = StringProperty()
    version = IntegerProperty()
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

    def save(self, **params):
        self.version = self.version + 1 if self.version else 1
        super(Application, self).save()


# The following classes are wrappers for the subparts of an application document
class DictWrapper(object):
#    def __getitem__(self, key):
#        return self._dict[key]
#    def __setitem__(self, key, val):
#        self._dict[key] = val
#    def update(self, *args, **kwargs):
#        return self._dict.update(*args, **kwargs)
#    def get(self, *args, **kwargs):
#        return self._dict.get(*args, **kwargs)
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
        assert(app.domain == self.name)
        return app