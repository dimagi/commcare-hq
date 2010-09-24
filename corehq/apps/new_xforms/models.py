from django.db import models
from couchdbkit.ext.django.schema import *

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
    def get_modules(self):
        for i in range(len(self.modules)):
            yield Module(self, i)
    def get_module(self, i):
        return Module(self, i)
    def id(self):
        return self._id


# The following classes are wrappers for the subparts of an application document
class DictWrapper(object):
    def __getitem__(self, key):
        return self._dict[key]
    def __setitem__(self, key, val):
        self._dict[key] = val
    def update(self, *args, **kwargs):
        return self._dict.update(*args, **kwargs)
    def __eq__(self, other):
        try:
            return (self.id == other.id) and (self.parent == other.parent)
        except:
            return False
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