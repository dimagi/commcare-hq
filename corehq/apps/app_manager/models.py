from couchdbkit.ext.django.schema import *
from django.core.urlresolvers import reverse
from corehq.util import bitly
from corehq.util.webutils import URL_BASE, parse_int
from django.http import Http404
from copy import deepcopy
from corehq.apps.domain.models import Domain
from BeautifulSoup import BeautifulStoneSoup
from datetime import datetime

DETAIL_TYPES = ('case_short', 'case_long', 'ref_short', 'ref_long')


class XForm(Document):
    domain = StringProperty()
    xmlns = StringProperty()
    submit_time = DateTimeProperty()

class XFormGroup(DocumentSchema):
    "Aggregate of all XForms with the same xmlns"
    display_name = StringProperty()
    xmlns = StringProperty()

class IndexedSchema(DocumentSchema):
    def with_id(self, i, parent):
        self._i = i
        self._parent = parent
        return self
    @property
    def id(self):
        return self._i
    def __eq__(self, other):
        return other and (self.id == other.id) and (self._parent == other._parent)

class Form(IndexedSchema):
    name        = DictProperty()
    requires    = StringProperty(choices=["case", "referral", "none"], default="none")
    xform_id    = StringProperty()
    xmlns       = StringProperty()
    show_count  = BooleanProperty(default=False)

class DetailColumn(DocumentSchema):
    header  = DictProperty()
    model   = StringProperty()
    field   = StringProperty()
    format  = StringProperty()
    enum    = DictProperty()

class Detail(DocumentSchema):
    type = StringProperty()
    columns = SchemaListProperty(DetailColumn)

    def append_column(self, column):
        self.columns.append(column)
    def update_column(self, column_id, column):
        my_column = self.columns[column_id]

        my_column.model  = column.model
        my_column.field  = column.field
        my_column.format = column.format

        for lang in column.header:
            my_column.header[lang] = column.header[lang]

        for key in column.enum:
            for lang in column.enum[key]:
                my_column.enum[key][lang] = column.enum[key][lang]

    def delete_column(self, column_id):
        del self.columns[column_id]

class Module(IndexedSchema):
    name = DictProperty()
    case_name = DictProperty()
    ref_name = DictProperty()
    forms = SchemaListProperty(Form)
    details = SchemaListProperty(Detail)
    case_type = StringProperty()

    def get_forms(self):
        l = len(self.forms)
        for i, form in enumerate(self.forms):
            yield form.with_id(i%l, self)
    @parse_int([1])
    def get_form(self, i):
        return self.forms[i].with_id(i%len(self.forms), self)

    def get_detail(self, detail_type):
        for detail in self.details:
            if detail.type == detail_type:
                return detail
        raise Exception("Module %s has no detail type %s" % (self, detail_type))




class VersioningError(Exception):
    pass

class VersionedDoc(Document):
    domain = StringProperty()
    copy_of = StringProperty()
    version = IntegerProperty()
    short_url = StringProperty()

    @property
    def id(self):
        return self._id

    def save(self, **params):
        self.version = self.version + 1 if self.version else 1
        super(VersionedDoc, self).save()
        if not self.short_url:
            self.short_url = bitly.shorten(
                URL_BASE + reverse('corehq.apps.app_manager.views.download_jad', args=[self.domain, self._id])
            )
            super(VersionedDoc, self).save()
    def save_copy(self):
        copies = VersionedDoc.view('app_manager/applications', key=[self.domain, self._id, self.version]).all()
        if copies:
            copy = copies[0]
        else:
            copy = deepcopy(self.to_json())
            del copy['_id']
            del copy['_rev']
            del copy['short_url']
            cls = self.__class__
            copy = cls.wrap(copy)
            copy['copy_of'] = self._id
            copy.version -= 1
            copy.save()
        return copy
    def revert_to_copy(self, copy):
        """
        Replaces couch doc with a copy of the backup ("copy").
        Returns the another Application/RemoteApp referring to this
        updated couch doc. The returned doc should be used in place of
        the original doc, i.e. should be called as follows:
            app = revert_to_copy(app, copy)
        This is not ideal :(
        """
        if copy.copy_of != self._id:
            raise VersioningError("%s is not a copy of %s" % (copy, self))
        app = deepcopy(copy).to_json()
        app['_rev'] = self._rev
        app['_id'] = self._id
        app['version'] = self.version
        app['copy_of'] = None
        cls = self.__class__
        app = cls.wrap(app)
        app.save()
        return app

    def delete_copy(self, copy):
        if copy.copy_of != self._id:
            raise VersioningError("%s is not a copy of %s" % (copy, self))
        copy.delete()

class Application(VersionedDoc):
    modules = SchemaListProperty(Module)
    name = StringProperty()
    langs = StringListProperty()

    def get_modules(self):
        l = len(self.modules)
        for i,module in enumerate(self.modules):
            yield module.with_id(i%l, self)

    @parse_int([1])
    def get_module(self, i):
        return self.modules[i].with_id(i%len(self.modules), self)

    @classmethod
    def new_app(cls, domain, name):
        app = cls(domain=domain, modules=[], name=name, langs=["en"])
        return app

    def new_module(self, name, lang):
        self.modules.append(
            Module(
                name={lang: name},
                forms=[],
                case_type='',
                case_name={'en': "Case"},
                ref_name={'en': "Referral"},
                details=[Detail(type=detail_type, columns=[]) for detail_type in DETAIL_TYPES],
            )
        )
        return self.get_module(-1)
    def delete_module(self, module_id):
        del self.modules[int(module_id)]

    def new_form(self, module_id, name, attachment, lang):
        xform = _register_xform(self.domain, attachment=attachment)
        module = self.get_module(module_id)
        module['forms'].append(
            Form(
                name={lang: name},
                xform_id=xform._id,
                xmlns=xform.xmlns,
                form_requires="none",
            )
        )
        form = module.get_form(-1)
        return form
    def delete_form(self, module_id, form_id):
        module = self.get_module(module_id)
        del module['forms'][int(form_id)]

    def swap_langs(self, i, j):
        langs = self.langs
        langs.insert(i, langs.pop(j))
        self.langs = langs
    def swap_modules(self, i, j):
        modules = self.modules
        modules.insert(i, modules.pop(j))
        self.modules = modules
    def swap_detail_columns(self, module_id, detail_type, i, j):
        module = self.get_module(module_id)
        detail = module['details'][DETAIL_TYPES.index(detail_type)]
        columns = detail['columns']
        columns.insert(i, columns.pop(j))
        detail['columns'] = columns
    def swap_forms(self, module_id, i, j):
        forms = self.modules[module_id]['forms']
        forms.insert(i, forms.pop(j))
        self.modules[module_id]['forms'] = forms

class RemoteApp(VersionedDoc):
    profile_url = StringProperty()
    suite_url = StringProperty(default="http://")
    name = StringProperty()

    @classmethod
    def new_app(cls, domain, name):
        app = cls(domain=domain, name=name, langs=["en"])
        return app

class DomainError(Exception):
    pass



def get_app(domain, app_id):
    app = VersionedDoc.get(app_id)

    try:    Domain.objects.get(name=domain)
    except: raise DomainError("domain %s does not exist" % domain)

    if app.domain != domain:
        raise DomainError("%s not in domain %s" % (app._id, domain))
    cls = {'Application': Application, "RemoteApp": RemoteApp}[app.doc_type]
    app = cls.wrap(app.to_json())
    return app

def _register_xform(domain, attachment):
    if not isinstance(attachment, basestring):
        attachment = attachment.read()
    xform = XForm()
    soup = BeautifulStoneSoup(attachment)
    xform.xmlns = soup.find('instance').findChild()['xmlns']

    xform.submit_time = datetime.utcnow()
    xform.domain = domain

    xform.save()
    xform.put_attachment(attachment, 'xform.xml', content_type='text/xml')
    return xform