# coding=utf-8
from couchdbkit.ext.django.schema import *
from django.core.urlresolvers import reverse
from corehq.apps.users.util import cc_user_domain
from corehq.util import bitly
from dimagi.utils.web import get_url_base, parse_int
from copy import deepcopy
from corehq.apps.domain.models import Domain
from BeautifulSoup import BeautifulStoneSoup
from datetime import datetime
import hashlib
from django.template.loader import render_to_string
from zipfile import ZipFile, ZIP_DEFLATED
from StringIO import StringIO
from urllib2 import urlopen
from urlparse import urljoin
from corehq.apps.app_manager.jadjar import JadDict, sign_jar
from corehq.apps.domain.decorators import login_and_domain_required
from django.http import HttpResponseForbidden


from django.db import models
import random
from dimagi.utils.couch.database import get_db
import json
from lxml import etree as ET
from dimagi.utils.make_uuid import random_hex


DETAIL_TYPES = ['case_short', 'case_long', 'ref_short', 'ref_long']

def _dsstr(self):
    return ", ".join(json.dumps(self.to_json()), self.schema)
#DocumentSchema.__repr__ = _dsstr

NS = dict(
    jr = "{http://openrosa.org/javarosa}",
    xsd = "{http://www.w3.org/2001/XMLSchema}",
    h='{http://www.w3.org/1999/xhtml}',
    f='{http://www.w3.org/2002/xforms}',
    ev="{http://www.w3.org/2001/xml-events}", 
    orx="{http://openrosa.org/jr/xforms}",
)

def _make_elem(tag, attr):
    return ET.Element(tag, dict([(key.format(**NS), val) for key,val in attr.items()]))

class JadJar(Document):
    """
    Has no properties except two attachments: CommCare.jad and CommCare.jar
    Meant for saving the jad and jar exactly as they come from the build server.

    """
    @property
    def hash(self):
        return self._id
    @classmethod
    def new(cls, jad, jar):
        try: jad = jad.read()
        except: pass
        try: jar = jar.read()
        except: pass
        hash = hashlib.sha1()
        hash.update(jad)
        hash.update(jar)
        hash = hash.hexdigest()
        try:
            jadjar = cls.get(hash)
        except:
            jadjar = cls(_id=hash)
            jadjar.save()
            jadjar.put_attachment(jad, 'CommCare.jad', 'text/vnd.sun.j2me.app-descriptor')
            jadjar.put_attachment(jar, 'CommCare.jar', 'application/java-archive')
        return jadjar
    def fetch_jad(self):
        return self.fetch_attachment('CommCare.jad')
    def fetch_jar(self):
        return self.fetch_attachment('CommCare.jar')
    def jad_dict(self):
        return JadDict.from_jad(self.fetch_jad())

def authorize_xform_edit(view):
    def authorized_view(request, xform_id):
        @login_and_domain_required
        def wrapper(req, domain):
            pass
        _, app = Form.get_form(xform_id, and_app=True)
        if wrapper(request, app.domain):
            # If login_and_domain_required intercepted wrapper
            # and returned an HttpResponse of its own
            #return HttpResponseForbidden()
            return wrapper(request, app.domain)
        else:
            return view(request, xform_id)
    return authorized_view

def get_xform(form_unique_id):
    "For use with xep_hq_server's GET_XFORM hook."
    form = Form.get_form(form_unique_id)
    return form.contents
def put_xform(form_unique_id, contents):
    "For use with xep_hq_server's PUT_XFORM hook."
    form, app = Form.get_form(form_unique_id, and_app=True)
    form.contents = contents
    form.refresh()
    app.save()

class IndexedSchema(DocumentSchema):
    """
    Abstract class.
    Meant for documents that appear in a list within another document
    and need to know their own position within that list.

    """
    def with_id(self, i, parent):
        self._i = i
        self._parent = parent
        return self
    @property
    def id(self):
        return self._i
    def __eq__(self, other):
        return other and (self.id == other.id) and (self._parent == other._parent)

class FormActionCondition(DocumentSchema):
    """
    The condition under which to open/update/close a case/referral

    Either {'type': 'if', 'question': '/xpath/to/node', 'answer': 'value'}
    in which case the action takes place if question has answer answer,
    or {'type': 'always'} in which case the action always takes place.
    """
    type        = StringProperty(choices=["if", "always", "never"], default="never")
    question    = StringProperty()
    answer      = StringProperty()

class FormAction(DocumentSchema):
    """
    Corresponds to Case XML

    """
    condition   = SchemaProperty(FormActionCondition)
    def is_active(self):
        return self.condition.type in ('if', 'always')

class UpdateCaseAction(FormAction):
    update  = DictProperty()
class OpenReferralAction(FormAction):
    name_path   = StringProperty()
class OpenCaseAction(FormAction):
    name_path   = StringProperty()
class UpdateReferralAction(FormAction):
    followup_date   = StringProperty()
class FormActions(DocumentSchema):
    open_case       = SchemaProperty(OpenCaseAction)
    update_case     = SchemaProperty(UpdateCaseAction)
    close_case      = SchemaProperty(FormAction)
    open_referral   = SchemaProperty(OpenReferralAction)
    update_referral = SchemaProperty(FormAction)
    close_referral  = SchemaProperty(UpdateReferralAction)

class Form(IndexedSchema):
    """
    Part of a Managed Application; configuration for a form.
    Translates to a second-level menu on the phone

    """

    name        = DictProperty()
    unique_id   = StringProperty()
    requires    = StringProperty(choices=["case", "referral", "none"], default="none")
    actions     = SchemaProperty(FormActions)
    show_count  = BooleanProperty(default=False)
    xmlns       = StringProperty()
    contents    = StringProperty()
    put_in_root = BooleanProperty(default=False)

    @classmethod
    def get_form(cls, form_unique_id, and_app=False):
        d = get_db().view('app_manager/xforms_index', key=form_unique_id).one()['value']
        # unpack the dict into variables app_id, module_id, form_id
        app_id, module_id, form_id = [d[key] for key in ('app_id', 'module_id', 'form_id')]

        app = Application.get(app_id)
        form = app.get_module(module_id).get_form(form_id)
        if and_app:
            return form, app
        else:
            return form
    def get_unique_id(self):
        if not self.unique_id:
            self.unique_id = hex(random.getrandbits(160))[2:-1]
            self._parent._parent.save()
        return self.unique_id
        
    def refresh(self):
        pass
        soup = BeautifulStoneSoup(self.contents)
        try:
            self.xmlns = soup.find('instance').findChild()['xmlns']
        except:
            self.xmlns = hashlib.sha1(self.get_unique_id()).hexdigest()
    def get_case_type(self):
        return self._parent.case_type
    
    def get_contents(self):
        if self.contents:
            contents = self.contents
        else:
            try:
                contents = self.fetch_attachment('xform.xml')
            except:
                contents = ""
        return contents
    def active_actions(self):
        actions = {}
        for action_type in (
            'open_case', 'update_case', 'close_case',
            'open_referral', 'update_referral', 'close_referral'
        ):
            a = getattr(self.actions, action_type)
            if a.is_active():
                actions[action_type] = a
        return actions

    
    def create_casexml(self):
        from xml_utils import XMLTag as __
        actions = self.active_actions()
        # a list of functions to be applied to the file as a whole after it has been pieced together
        additional_transformations = []

        if not actions:
            casexml_text, binds = "", []
        else:
            binds = []
            def add_bind(d):
                binds.append(_make_elem('bind', d))
            casexml = __('case')[
                __("case_id"),
                __("date_modified")
            ]

            add_bind({"nodeset":"case/date_modified", "type":"dateTime", "{jr}preload":"timestamp", "{jr}preloadParams":"end"})


            def relevance(action):
                if action.condition.type == 'always':
                    return 'true()'
                elif action.condition.type == 'if':
                    return "%s = '%s'" % (action.condition.question, action.condition.answer)
                else:
                    return 'false()'
            if 'open_case' in actions:
                casexml[
                    __('create')[
                        __("case_type_id")[self.get_case_type()],
                        __("case_name"),
                        __("user_id"),
                    ]
                ]
                r = relevance(actions['open_case'])
                add_bind({
                    "nodeset":"case/case_id",
                    "{jr}preload":"uid",
                    "{jr}preloadParams":"general",
                    "relevant": r,
                })
                add_bind({
                    'nodeset':"case/create/user_id",
                    'type':"xsd:string",
                    '{jr}preload': "meta",
                    '{jr}preloadParams': "UserID",
                    "relevant": r,
                })
                add_bind({
                    "nodeset":"case/create/case_name",
                    "calculate":actions['open_case'].name_path,
                    "relevant": r,
                })
                def require_case_name_source(xml, xmlns):
                    "make sure that the question that provides the case_name is required"
                    name_path = actions['open_case'].name_path
                    name_bind_path = ('.//{f}bind[@nodeset="%s"]' % name_path).format(**NS)
                    name_bind = xml.find(name_bind_path)
                    name_bind.attrib['required'] = "true()"
                additional_transformations.append(require_case_name_source)

            else:
                add_bind({"nodeset":"case/case_id", "{jr}preload":"case", "{jr}preloadParams":"case-id"})
            if 'update_case' in actions:
                # no condition
                casexml[
                    __('update')[
                        (__(key) for key in actions['update_case'].update.keys())
                    ]
                ]
                for key, path in actions['update_case'].update.items():
                    add_bind({"nodeset":"case/update/%s" % key, "calculate": path})
            if 'close_case' in actions:
                casexml[
                    __('close')
                ]
                r = relevance(actions['close_case'])
                add_bind({
                    "nodeset": "case/close",
                    "relevant": r,
                })

            if 'open_referral' in actions or 'update_referral' in actions or 'close_referral' in actions:
                referral = __('referral')[
                    __('referral_id'),
                ]
                if 'open_referral' in actions or 'update_referral' in actions:
                    referral[__('followup_date')]
                casexml[referral]

                if 'open_referral' in actions:
                    # no condition
                    referral[
                        __("open")[
                            __("referral_types")
                        ]
                    ]
                    add_bind({
                        "nodeset":"case/referral",
                        "relevant":"count-selected(%s) > 0" % actions['open_referral'].name_path
                    })
                    add_bind({
                        "nodeset":"case/referral/referral_id",
                        "{jr}preload":"uid",
                        "{jr}preloadParams":"general",
                    })
                    add_bind({
                        "nodeset":"case/referral/followup_date",
                        "type":"date",
                        "calculate": "date(today() + 2)"
                    })
                    add_bind({
                        "nodeset":"case/referral/open/referral_types",
                        "calculate": actions['open_referral'].name_path,
                    })
                if 'update_referral' in actions or 'close_referral' in actions:
                    # no condition
                    referral_update = __("update")[
                        __("referral_type")
                    ]
                    referral[referral_update]

                    add_bind({
                        "nodeset":"case/referral/referral_id",
                        "{jr}preload":"patient_referral",
                        "{jr}preloadParams":"id"
                    })
                    add_bind({
                        "nodeset":"case/referral/update/referral_type",
                        "{jr}preload":"patient_referral",
                        "{jr}preloadParams":"type"
                    })

                if 'update_referral' in actions:
                    # no condition
                    add_bind({
                        "nodeset": "case/referral/followup_date",
                        "type":"xsd:date",
                        "calculate": "if(date(%(followup_date)s) >= date(today() + 2), %(followup_date)s, date(today() + 2))" % {
                            'followup_date': actions['update_referral'].followup_date,
                        },
                    })
                if 'close_referral' in actions:
                    referral_update[__("date_closed")]
                    r = relevance(actions['close_referral'])
                    add_bind({
                        "nodeset":"case/referral/update/date_closed",
                        "relevant": r,
                        "{jr}preload":"timestamp",
                        "{jr}preloadParams":"end"
                    })
            casexml_text = casexml.render()
        def transformation(xml, xmlns):
            for trans in additional_transformations:
                trans(xml, xmlns)
        return casexml_text, binds, transformation


    def get_questions(self, langs):
        """
        parses out the questions from the xform, into the format:
        [
            {
                "label": label,
                "tag": tag,
                "value": value,
            },
            ...
        ]

        if the xform is bad, it will raise an XMLSyntaxError

        """        
        #<hack>
        xform = self.contents.replace('xmlns=""', '')
        if xform != self.contents:
            self.contents = xform
            self._parent._parent.save()
        #</hack>

        if not xform:
            return []

        # "Unicode strings with encoding declaration are not supported."
        tree = ET.fromstring(xform.encode('utf-8'))


        NS = {'h': '{http://www.w3.org/1999/xhtml}', 'f': '{http://www.w3.org/2002/xforms}'}
        def lookup_translation(s,pre = 'jr:itext(', post = ')'):
            if s.startswith(pre) and post[-len(post):] == post:
                s = s[len(pre):-len(post)]
            if s[0] == s[-1] and s[0] in ('"', "'"):
                id = s[1:-1]
            for lang in langs:
                x = tree.find('.//{f}translation[@lang="%s"]'.format(**NS) % lang)
                if x is not None:
                    break
            if x is None:
                x = tree.find('.//{f}translation'.format(**NS))
            x = x.find('{f}text[@id="%s"]'.format(**NS) % id)
            x = x.findtext('{f}value'.format(**NS)).strip()
            return x
        def get_ref(elem):
            try:
                ref = elem.attrib['ref']
            except:
                bind_id = elem.attrib['bind']
                bind = tree.find('.//{f}bind[@id="%s"]'.format(**NS) % bind_id)
                ref = bind.attrib['nodeset']
            return ref
        questions = []
        # TODO: make this include everything but triggers; include things in groups
        for elem in tree.findall('{h}body/*'.format(**NS)):
            try:
                label_ref = elem.find('{f}label'.format(**NS)).attrib['ref']
            except:
                label_ref = None
            if label_ref:
                question = {
                    "label": lookup_translation(label_ref),
                    "tag": elem.tag.split('}')[-1],
                    "value": get_ref(elem),
                }
            else:
                continue
            if question['tag'] == "select1":
                options = []
                for item in elem.findall('{f}item'.format(**NS)):
                    try:
                        translation = lookup_translation(item.find('{f}label'.format(**NS)).attrib['ref'])
                    except:
                        translation = "(No label)"
                    options.append({
                        'label': translation,
                        'value': item.findtext('{f}value'.format(**NS)).strip()
                    })
                question.update({'options': options})
            questions.append(question)
#        if not questions:
#            questions = [{"label": "Unable to get questions from xform", "tag": "", "value": ""}]
        return questions
    
    def export_json(self):
        source = self.to_json()
        del source['unique_id']
        return source

class DetailColumn(IndexedSchema):
    """
    Represents a column in case selection screen on the phone. Ex:
        {
            'header': {'en': 'Sex', 'pt': 'Sexo'},
            'model': 'cc_pf_client',
            'field': 'sex',
            'format': 'enum',
            'enum': {'en': {'m': 'Male', 'f': 'Female'}, 'pt': {'m': 'Macho', 'f': 'Fêmea'}}
        }

    """
    header  = DictProperty()
    model   = StringProperty()
    field   = StringProperty()
    format  = StringProperty()
    enum    = DictProperty()

class Detail(DocumentSchema):
    """
    Full configuration for a case selection screen

    """
    type = StringProperty(choices=DETAIL_TYPES)
    columns = SchemaListProperty(DetailColumn)


    def get_columns(self):
        l = len(self.columns)
        for i, column in enumerate(self.columns):
            yield column.with_id(i%l, self)
    @parse_int([1])
    def get_column(self, i):
        return self.columns[i].with_id(i%len(self.columns), self)
    
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
    """
    A group of related forms, and configuration that applies to them all.
    Translates to a top-level menu on the phone.

    """
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

    def infer_case_type(self):
        case_types = []
        for form in self.forms:
            xform = form.contents
            soup = BeautifulStoneSoup(xform)
            try:
                case_type = soup.find('case').find('case_type_id').string.strip()
            except AttributeError:
                case_type = None
            if case_type:
                case_types.append(case_type)
        return case_types

    def export_json(self):
        source = self.to_json()
        for form in source['forms']:
            del form['unique_id']
        return source
    def requires(self):
        r = set(["none"])
        for form in self.get_forms():
            r.add(form.requires)
        for val in ("referral", "case", "none"):
            if val in r:
                return val
    def detail_types(self):
        return {
            "referral": ["case_short", "case_long", "ref_short", "ref_long"],
            "case": ["case_short", "case_long"],
            "none": []
        }[self.requires()]

class VersioningError(Exception):
    """For errors that violate the principals of versioning in VersionedDoc"""
    pass

class VersionedDoc(Document):
    """
    A document that keeps an auto-incrementing version number, knows how to make copies of itself,
    delete a copy of itself, and revert back to an earlier copy of itself.

    """
    domain = StringProperty()
    copy_of = StringProperty()
    version = IntegerProperty()
    short_url = StringProperty()

    _meta_fields = ['_id', '_rev', 'domain', 'copy_of', 'version', 'short_url']

    @property
    def id(self):
        return self._id

    def save(self, response_json=None, **params):
        self.version = self.version + 1 if self.version else 1
        super(VersionedDoc, self).save()
        if not self.short_url:
            self.short_url = bitly.shorten(
                get_url_base() + reverse('corehq.apps.app_manager.views.download_jad', args=[self.domain, self._id])
            )
            super(VersionedDoc, self).save()
        if response_json is not None:
            if 'update' not in response_json:
                response_json['update'] = {}
            response_json['update']['.variable-version'] = self.version
    def save_copy(self):
        copies = VersionedDoc.view('app_manager/applications', key=[self.domain, self._id, self.version]).all()
        if copies:
            copy = copies[0]
        else:
            copy = deepcopy(self.to_json())
            del copy['_id']
            del copy['_rev']
            del copy['short_url']
            if "recipients" in copy:
                del copy['recipients']
            if '_attachments' in copy:
                del copy['_attachments']
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
        del app['_attachments']
        cls = self.__class__
        app = cls.wrap(app)
        app.save()
        return app

    def delete_copy(self, copy):
        if copy.copy_of != self._id:
            raise VersioningError("%s is not a copy of %s" % (copy, self))
        copy.delete()
    
    def scrub_source(self, source):
        """
        To be overridden.
        
        Use this to scrub out anything
        that should be shown in the
        application source, such as ids, etc.
        
        """
        pass

    def export_json(self):
        source = self.to_json()
        
        for field in self._meta_fields:
            if field in source:
                del source[field]
        self.scrub_source(source)
        return source
    @classmethod
    def from_source(cls, source, domain):
        for field in cls._meta_fields:
            if field in source:
                del source[field]
        source['domain'] = domain
        return cls.wrap(source)
        


class ApplicationBase(VersionedDoc):
    """
    Abstract base class for Application and RemoteApp.
    Contains methods for generating the various files and zipping them into CommCare.jar

    """

    recipients = StringProperty(default="")

    @property
    def post_url(self):
        return "%s%s" % (
            get_url_base(),
            reverse('corehq.apps.receiver.views.post', args=[self.domain])
        )
    @property
    def ota_restore_url(self):
        return "%s%s" % (
            get_url_base(),
            reverse('corehq.apps.phone.views.restore', args=[self.domain])
        )
    @property
    def profile_url(self):
        return "%s%s" % (
            get_url_base(),
            reverse('corehq.apps.app_manager.views.download_profile', args=[self.domain, self._id])
        )
    @property
    def profile_loc(self):
        return "jr://resource/profile.xml"
    @property
    def jar_url(self):
        return "%s%s" % (
            get_url_base(),
            reverse('corehq.apps.app_manager.views.download_zipped_jar', args=[self.domain, self._id]),
        )
    def get_jadjar(self):
        return JadJar.view('app_manager/jadjar', descending=True).all()[0]

    def create_jad(self, template="app_manager/CommCare.jad"):
        try:
            return self.fetch_attachment('CommCare.jad')
        except:
            jad = self.get_jadjar().jad_dict()
            jar = self.create_zipped_jar()
            jad.update({
                'MIDlet-Jar-Size': len(jar),
                'Profile': self.profile_loc,
                'MIDlet-Jar-URL': self.jar_url,
                #'MIDlet-Name': self.name,
            })
            jad = sign_jar(jad, jar)
            jad = jad.render()
            self.put_attachment(jad, 'CommCare.jad')
            return jad

    def create_profile(self, template='app_manager/profile.xml'):
        return render_to_string(template, {
            'app': self,
            'suite_url': self.suite_url,
            'suite_loc': self.suite_loc,
            'post_url': self.post_url,
            'post_test_url': self.post_url,
            'ota_restore_url': self.ota_restore_url,
            'cc_user_domain': cc_user_domain(self.domain)
        }).decode('utf-8')
    def fetch_jar(self):
        return self.get_jadjar().fetch_jar()

    def create_zipped_jar(self):
        try:
            return self.fetch_attachment('CommCare.jar')
        except:
            jar = self.fetch_jar()
            files = self.create_all_files()
            buffer = StringIO(jar)
            zipper = ZipFile(buffer, 'a', ZIP_DEFLATED)
            for path in files:
                zipper.writestr(path, files[path].encode('utf-8'))
            zipper.close()
            buffer.flush()
            jar = buffer.getvalue()
            buffer.close()
            self.put_attachment(jar, 'CommCare.jar', content_type="application/java-archive")
            return jar
    def validate_app(self):
        return []
    
class Application(ApplicationBase):
    """
    A Managed Application that can be created entirely through the online interface, except for writing the
    forms themselves.

    """
    modules = SchemaListProperty(Module)
    name = StringProperty()
    langs = StringListProperty()
    use_commcare_sense = BooleanProperty(default=False)

    @property
    def suite_url(self):
        return "%s%s" % (
            get_url_base(),
            reverse('corehq.apps.app_manager.views.download_suite', args=[self.domain, self._id])
        )
    @property
    def suite_loc(self):
        return "suite.xml"
#    @property
#    def jar_url(self):
#        return "%s%s" % (
#            get_url_base(),
#            reverse('corehq.apps.app_manager.views.download_zipped_jar', args=[self.domain, self._id]),
#        )

    def fetch_xform(self, module_id, form_id, DEBUG=False):
        form = self.get_module(module_id).get_form(form_id)
        tree = ET.fromstring(form.contents.encode('utf-8'))
        def fmt(s):
            return s.format(
                x='{%s}' % form.xmlns,
                **NS
            )
        case = tree.find(fmt('.//{f}model/{f}instance/*/{x}case'))
        
        case_parent = tree.find(fmt('.//{f}model/{f}instance/*'))
        bind_parent = tree.find(fmt('.//{f}model/'))
        
        casexml, binds, transformation = form.create_casexml()
        if casexml:
            if case is not None:
                case_parent.remove(case)
            # casexml has to be valid, 'cuz *I* made it
            casexml = ET.fromstring(casexml)
            case_parent.append(casexml)
            if DEBUG: tree = ET.fromstring(ET.tostring(tree))
            for bind in bind_parent.findall(fmt('{f}bind')):
                if bind.attrib['nodeset'].startswith('case/'):
                    bind_parent.remove(bind)
            for bind in binds:
                if DEBUG:
                    xpath = ".//{x}" + bind.attrib['nodeset'].replace("/", "/{x}")
                    if tree.find(fmt(xpath)) is None:
                        raise Exception("Invalid XPath Expression %s" % xpath)
                bind_parent.append(bind)

        if case_parent.find(fmt('{orx}meta')) is None:
            orx = fmt("{orx}")[1:-1]
            nsmap = {"orx": orx}
            meta = ET.Element(fmt("{orx}meta"), nsmap=nsmap)
            for tag in ('deviceID','timeStart', 'timeEnd','username','userID','uid'):
                meta.append(ET.Element(fmt("{orx}%s")%tag, nsmap=nsmap))
            case_parent.append(meta)
            id = form.unique_id + "meta"
            binds = [
                {"id": "%s1" % id, "nodeset": "meta/deviceID", "type": "xsd:string", "{jr}preload": "property", "{jr}preloadParams": "DeviceID"},
                {"id": "%s2" % id, "nodeset": "meta/timeStart", "type": "xsd:dateTime", "{jr}preload": "timestamp", "{jr}preloadParams": "start"},
                {"id": "%s3" % id, "nodeset": "meta/timeEnd", "type": "xsd:dateTime", "{jr}preload": "timestamp", "{jr}preloadParams": "end"},
                {"id": "%s4" % id, "nodeset": "meta/username", "type": "xsd:string", "{jr}preload": "meta", "{jr}preloadParams": "UserName"},
                {"id": "%s5" % id, "nodeset": "meta/userID", "type": "xsd:string", "{jr}preload": "meta", "{jr}preloadParams": "UserID"},
                {"id": "%s6" % id, "nodeset": "meta/uid", "type": "xsd:string", "{jr}preload": "uid", "{jr}preloadParams": "general"},
            ]
            for bind in binds:
                bind = _make_elem('bind', bind)
                bind_parent.append(bind)

        # apply any other transformations
        # necessary to make casexml work
        transformation(tree, form.xmlns)
        return ET.tostring(tree)

    def create_app_strings(self, lang, template='app_manager/app_strings.txt'):
        return render_to_string(template, {
            'app': self,
            'langs': [lang] + self.langs,
        })
    def create_suite(self, template='app_manager/suite.xml'):
        return render_to_string(template, {
            'app': self,
            'langs': ["default"] + self.langs
        })

    def create_all_files(self):
        files = {
            "profile.xml": self.create_profile(),
            "suite.xml": self.create_suite(),
        }

        for lang in ['default'] + self.langs:
            files["%s/app_strings.txt" % lang] = self.create_app_strings(lang)
        for module in self.get_modules():
            for form in module.get_forms():
                files["m%s/f%s.xml" % (module.id, form.id)] = self.fetch_xform(module.id, form.id)
        return files

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
                name={lang if lang else "en": name if name else "Untitled Module"},
                forms=[],
                case_type='',
                case_name={'en': "Case"},
                ref_name={'en': "Referral"},
                details=[Detail(type=detail_type, columns=[]) for detail_type in DETAIL_TYPES],
            )
        )
        return self.get_module(-1)
        
    def new_module_from_source(self, source):
        self.modules.append(Module.wrap(source))
        return self.get_module(-1)
    
    def delete_module(self, module_id):
        del self.modules[int(module_id)]

    def new_form(self, module_id, name, lang, attachment=""):
        module = self.get_module(module_id)
        form = Form(
            name={lang if lang else "en": name if name else "Untitled Form"},
            contents=attachment,
        )
        module.forms.append(form)
        form = module.get_form(-1)
        form.refresh()
        case_types = module.infer_case_type()
        if len(case_types) == 1 and not module.case_type:
            module.case_type, = case_types
        return form
    def new_form_from_source(self, module_id, source):
        module = self.get_module(module_id)
        module.forms.append(Form.wrap(source))
        form = module.get_form(-1)
        case_types = module.infer_case_type()
        if len(case_types) == 1 and not module.case_type:
            module.case_type, = case_types
        return form
    def delete_form(self, module_id, form_id):
        module = self.get_module(module_id)
        del module['forms'][int(form_id)]

    def rearrange_langs(self, i, j):
        langs = self.langs
        langs.insert(i, langs.pop(j))
        self.langs = langs
    def rearrange_modules(self, i, j):
        modules = self.modules
        modules.insert(i, modules.pop(j))
        self.modules = modules
    def rearrange_detail_columns(self, module_id, detail_type, i, j):
        module = self.get_module(module_id)
        detail = module['details'][DETAIL_TYPES.index(detail_type)]
        columns = detail['columns']
        columns.insert(i, columns.pop(j))
        detail['columns'] = columns
    def rearrange_forms(self, module_id, i, j):
        forms = self.modules[module_id]['forms']
        forms.insert(i, forms.pop(j))
        self.modules[module_id]['forms'] = forms
    def scrub_source(self, source):
        for m,module in enumerate(source['modules']):
            for f,form in enumerate(module['forms']):
                del source['modules'][m]['forms'][f]['unique_id']
    def validate_app(self):
        errors = []
        if not self.modules:
            errors.append({"type": "no modules"})
        for module in self.get_modules():
            if not module.forms:
                errors.append({'type': "no forms", "module": {"id": module.id, "name": module.name}})
            needs_case_type = False
            needs_case_detail = False
            needs_referral_detail = False

            for form in module.get_forms():
                try:
                    ET.fromstring(form.contents.encode('utf-8'))
                except Exception as e:
                    errors.append({
                        'type': "invalid xml",
                        "module": {"id": module.id, "name": module.name},
                        "form": {"id": form.id, "name": form.name},
                        'message': unicode(e),
                    })
                if form.requires in ('case', 'referral'):
                    needs_case_detail = True
                    needs_case_type = True
                if form.active_actions():
                    needs_case_type = True
                if form.requires == "referral":
                    needs_referral_detail = True
            if needs_case_type and not module.case_type:
                errors.append({'type': "no case type", "module": {"id": module.id, "name": module.name}})
            if needs_case_detail and not (module.get_detail('case_short').columns and module.get_detail('case_long').columns):
                errors.append({'type': "no case detail", "module": {"id": module.id, "name": module.name}})
            if needs_referral_detail and not (module.get_detail('ref_short').columns and module.get_detail('ref_long').columns):
                errors.append({'type': "no ref detail", "module": {"id": module.id, "name": module.name}})
        return errors
    
class NotImplementedYet(Exception):
    pass
class RemoteApp(ApplicationBase):
    """
    A wrapper for a url pointing to a suite or profile file. This allows you to
    write all the files for an app by hand, and then give the url to app_manager
    and let it package everything together for you.

    Originally I thought it would be easiest to start from the suite.xml file, but this
    means the profile is auto-generated, which isn't so good. I should probably get rid of
    suite_url altogether and just switch to using the profile_url (which right now is not used).

    """
    profile_url = StringProperty(default="http://")
    #suite_url = StringProperty()
    name = StringProperty()

    # @property
    #     def suite_loc(self):
    #         if self.suite_url:
    #             return self.suite_url.split('/')[-1]
    #         else:
    #             raise NotImplementedYet()

    @classmethod
    def new_app(cls, domain, name):
        app = cls(domain=domain, name=name, langs=["en"])
        return app

    # def fetch_suite(self):
    #     return urlopen(self.suite_url).read()
    def create_profile(self):
        return urlopen(self.profile_url).read()
        
    def fetch_file(self, location):
        base = '/'.join(self.profile_url.split('/')[:-1]) + '/'
        if location.startswith('./'):
            location = location.lstrip('./')
        elif location.startswith(base):
            location = location.lstrip(base)
        elif location.startswith('jr://resource/'):
            location = location.lstrip('jr://resource/')
        return location, urlopen(urljoin(self.profile_url, location)).read().decode('utf-8')
        
    def create_all_files(self):
        files = {
            'profile.xml': self.create_profile(),
        }
        tree = ET.fromstring(files['profile.xml'])
        suite_loc = tree.find('suite/resource/location[@authority="local"]').text
        suite_loc, suite = self.fetch_file(suite_loc)
        files[suite_loc] = suite
        soup = BeautifulStoneSoup(suite)
        locations = []
        for resource in soup.findAll('resource'):
            try:
                loc = resource.findChild('location', authority='remote').string
            except:
                loc = resource.findChild('location', authority='local').string
            locations.append(loc)
        for location in locations:
            files.update((self.fetch_file(location),))
        return files

class DomainError(Exception):
    pass



def get_app(domain, app_id):
    """
    Utility for getting an app, making sure it's in the domain specified, and wrapping it in the right class
    (Application or RemoteApp).

    """

    app = get_db().get(app_id)

    try:    Domain.objects.get(name=domain)
    except: raise DomainError("domain %s does not exist" % domain)

    if app['domain'] != domain:
        raise DomainError("%s not in domain %s" % (app._id, domain))
    cls = {'Application': Application, "RemoteApp": RemoteApp}[app['doc_type']]
    app = cls.wrap(app)
    return app

