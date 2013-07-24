# coding=utf-8
import tempfile
import os
import logging
import hashlib
import random
import json
import langcodes
import types
import re
from collections import defaultdict
from datetime import datetime
from functools import wraps
from copy import deepcopy
from urllib2 import urlopen
from urlparse import urljoin

from django.core.cache import cache
from django.utils.encoding import force_unicode
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext
from corehq.apps.app_manager.const import APP_V1, APP_V2
from couchdbkit.exceptions import BadValueError
from couchdbkit.ext.django.schema import *
from django.conf import settings
from django.contrib.auth.models import get_hexdigest
from django.core.urlresolvers import reverse
from django.http import Http404
from django.template.loader import render_to_string

from restkit.errors import ResourceError
from couchdbkit.resource import ResourceNotFound
from couchdbkit.exceptions import BadValueError
from couchdbkit.ext.django.schema import *

from dimagi.utils.couch.lazy_attachment_doc import LazyAttachmentDoc
from dimagi.utils.couch.undo import DeleteRecord, DELETED_SUFFIX
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import get_url_base, parse_int
from dimagi.utils.couch.database import get_db
import commcare_translations

from corehq.util import bitly
from corehq.apps.receiverwrapper.models import Repeater, register_repeater_type
from corehq.apps.appstore.models import SnapshotMixin
from corehq.apps.builds.models import BuildSpec, CommCareBuildConfig, BuildRecord
from corehq.apps.hqmedia.models import HQMediaMixin
from corehq.apps.reports.templatetags.timezone_tags import utc_to_timezone
from corehq.apps.translations.models import TranslationMixin
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import cc_user_domain
from corehq.apps.domain.models import cached_property

from corehq.apps.app_manager import current_builds
from corehq.apps.app_manager.const import APP_V1, APP_V2
from corehq.apps.app_manager import fixtures, suite_xml, commcare_settings, build_error_utils
from corehq.apps.app_manager.suite_xml import IdStrings
from corehq.apps.app_manager.templatetags.xforms_extras import clean_trans
from corehq.apps.app_manager.util import split_path, save_xform
from corehq.apps.app_manager.xform import XForm, parse_xml as _parse_xml, XFormError, XFormValidationError, WrappedNode, CaseXPath

MISSING_DEPENDECY = \
"""Aw shucks, someone forgot to install the google chart library
on this machine and this feature needs it. To get it, run
easy_install pygooglechart.  Until you do that this won't work.
"""

DETAIL_TYPES = ['case_short', 'case_long', 'ref_short', 'ref_long']

CASE_PROPERTY_MAP = {
    # IMPORTANT: if you edit this you probably want to also edit
    # the corresponding map in cloudcare 
    # (corehq.apps.cloudcare.static.cloudcare.js.backbone.cases.js)
    'external-id': 'external_id',
    'date-opened': 'date_opened',
    'status': '@status',
    'name': 'case_name',
}

ATTACHMENT_REGEX = r'[^/]*\.xml'


def _rename_key(dct, old, new):
    if old in dct:
        if new in dct and dct[new]:
            dct["%s_backup_%s" % (new, hex(random.getrandbits(32))[2:-1])] = dct[new]
        dct[new] = dct[old]
        del dct[old]

@memoized
def load_case_reserved_words():
    with open(os.path.join(os.path.dirname(__file__), 'static', 'app_manager', 'json', 'case-reserved-words.json')) as f:
        return json.load(f)

@memoized
def load_default_user_registration():
    with open(os.path.join(os.path.dirname(__file__), 'data', 'register_user.xhtml')) as f:
        return f.read()


def partial_escape(xpath):
    """
    Copied from http://stackoverflow.com/questions/275174/how-do-i-perform-html-decoding-encoding-using-python-django
    but without replacing the single quote

    """
    return mark_safe(force_unicode(xpath).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;'))

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

    class Getter(object):
        def __init__(self, attr):
            self.attr = attr
        def __call__(self, instance):
            items = getattr(instance, self.attr)
            l = len(items)
            for i,item in enumerate(items):
                yield item.with_id(i%l, instance)
        def __get__(self, instance, owner):
            # thanks, http://metapython.blogspot.com/2010/11/python-instance-methods-how-are-they.html
            # this makes Getter('foo') act like a bound method
            return types.MethodType(self, instance, owner)


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

class PreloadAction(FormAction):
    preload = DictProperty()
    def is_active(self):
        return bool(self.preload)

class UpdateReferralAction(FormAction):
    followup_date   = StringProperty()
    def get_followup_date(self):
        if self.followup_date:
            return "if(date({followup_date}) >= date(today()), {followup_date}, date(today() + 2))".format(
                followup_date = self.followup_date,
            )
        return self.followup_date or "date(today() + 2)"


class OpenReferralAction(UpdateReferralAction):
    name_path = StringProperty()


class OpenCaseAction(FormAction):
    name_path = StringProperty()
    external_id = StringProperty()


class OpenSubCaseAction(FormAction):
    case_type = StringProperty()
    case_name = StringProperty()
    case_properties = DictProperty()
    repeat_context = StringProperty()


class FormActions(DocumentSchema):
    open_case = SchemaProperty(OpenCaseAction)
    update_case = SchemaProperty(UpdateCaseAction)
    close_case = SchemaProperty(FormAction)
    open_referral = SchemaProperty(OpenReferralAction)
    update_referral = SchemaProperty(UpdateReferralAction)
    close_referral = SchemaProperty(FormAction)

    case_preload = SchemaProperty(PreloadAction)
    referral_preload = SchemaProperty(PreloadAction)

    subcases = SchemaListProperty(OpenSubCaseAction)

    def all_property_names(self):
        names = set()
        names.update(self.update_case.update.keys())
        names.update(self.case_preload.preload.values())
        for subcase in self.subcases:
            names.update(subcase.case_properties.keys())
        return names


class FormSource(object):
    def __get__(self, form, form_cls):
        unique_id = form.get_unique_id()
        app = form.get_app()
        filename = "%s.xml" % unique_id

        # for backwards compatibility of really old apps
        try:
            old_contents = form['contents']
        except AttributeError:
            pass
        else:
            app.lazy_put_attachment(old_contents, filename)
            del form['contents']

        try:
            source = app.lazy_fetch_attachment(filename)
        except (ResourceNotFound, KeyError):
            source = ''

        return source

    def __set__(self, form, value):
        unique_id = form.get_unique_id()
        app = form.get_app()
        filename = "%s.xml" % unique_id
        app.lazy_put_attachment(value, filename)
        form.validation_cache = None
        try:
            form.xmlns = form.wrapped_xform().data_node.tag_xmlns
        except Exception:
            form.xmlns = None


class CachedStringProperty(object):
    def __init__(self, key):
        self.get_key = key

    def __get__(self, instance, owner):
        return self.get(self.get_key(instance))

    def __set__(self, instance, value):
        self.set(self.get_key(instance), value)

    @classmethod
    def get(cls, key):
        return cache.get(key)

    @classmethod
    def set(cls, key, value):
        cache.set(key, value, 12*60*60)


class CouchCache(Document):
    value = StringProperty(default=None)


class CouchCachedStringProperty(CachedStringProperty):

    @classmethod
    def _get(cls, key):
        try:
            c = CouchCache.get(key)
            assert(c.doc_type == CouchCache.__name__)
        except ResourceNotFound:
            c = CouchCache(_id=key)
        return c

    @classmethod
    def get(cls, key):
        return cls._get(key).value

    @classmethod
    def set(cls, key, value):
        c = cls._get(key)
        c.value = value
        c.save()


class FormBase(DocumentSchema):
    """
    Part of a Managed Application; configuration for a form.
    Translates to a second-level menu on the phone

    """

    name = DictProperty()
    unique_id = StringProperty()
    requires = StringProperty(choices=["case", "referral", "none"], default="none")
    actions = SchemaProperty(FormActions)
    show_count = BooleanProperty(default=False)
    xmlns = StringProperty()
    version = IntegerProperty()
    source = FormSource()
    validation_cache = CouchCachedStringProperty(
        lambda self: "cache-%s-%s-validation" % (self.get_app().get_id, self.unique_id)
    )

    @classmethod
    def wrap(cls, data):
        data.pop('validation_cache', '')
        return super(FormBase, cls).wrap(data)

    @classmethod
    def generate_id(cls):
        return hex(random.getrandbits(160))[2:-1]

    @classmethod
    def get_form(cls, form_unique_id, and_app=False):

        d = get_db().view('app_manager/xforms_index', key=form_unique_id).one()
        if d:
            d = d['value']
        else:
            raise ResourceNotFound()
        # unpack the dict into variables app_id, module_id, form_id
        app_id, unique_id = [d[key] for key in ('app_id', 'unique_id')]

        app = Application.get(app_id)
        form = app.get_form(unique_id)
        if and_app:
            return form, app
        else:
            return form

    def wrapped_xform(self):
        return XForm(self.source)

    def validate_form(self):
        vc = self.validation_cache
        if vc is None:
            try:
                XForm(self.source).validate(version=self.get_app().application_version)
            except XFormValidationError as e:
                validation_dict = {
                    "fatal_error": e.fatal_error,
                    "validation_problems": e.validation_problems,
                    "version": e.version,
                }
                vc = self.validation_cache = json.dumps(validation_dict)
            else:
                vc = self.validation_cache = ""
        if vc:
            try:
                raise XFormValidationError(**json.loads(vc))
            except ValueError:
                self.validation_cache = None
                return self.validate_form()
        return self

    def validate_for_build(self):
        errors = []
        needs_case_type = False
        needs_case_detail = False
        needs_referral_detail = False

        try:
            module = self.get_module()
        except AttributeError:
            module = None
            form_type = 'user_registration'
        else:
            form_type = 'module_form'

        meta = {
            'form_type': form_type,
            'module': build_error_utils.get_module_info(module) if module else {},
            'form': {"id": self.id if hasattr(self, 'id') else None, "name": self.name}
        }

        try:
            _parse_xml(self.source)
        except XFormError as e:
            errors.append(dict(
                type="invalid xml",
                message=unicode(e) if self.source else '',
                **meta
            ))
        except ValueError:
            logging.error("Failed: _parse_xml(string=%r)" % self.source)
            raise
        else:
            for error in self.check_actions():
                error.update(meta)
                errors.append(error)

        if self.requires_case():
            needs_case_detail = True
            needs_case_type = True
        if self.requires_case_type():
            needs_case_type = True
        if self.requires_referral():
            needs_referral_detail = True

        if module:
            errors.extend(
                build_error_utils.get_case_errors(
                    module,
                    needs_case_type=needs_case_type,
                    needs_case_detail=needs_case_detail,
                    needs_referral_detail=needs_referral_detail,
                )
            )

        return errors

    def get_unique_id(self):
        """
        Return unique_id if it exists, otherwise initialize it

        Does _not_ force a save, so it's the caller's responsibility to save the app

        """
        if not self.unique_id:
            self.unique_id = FormBase.generate_id()
        return self.unique_id

    def get_app(self):
        return self._app

    def get_case_type(self):
        return self._parent.case_type

    def get_version(self):
        return self.version if self.version else self.get_app().version

    def add_stuff_to_xform(self, xform):
        app = self.get_app()
        xform.exclude_languages(app.build_langs)
        xform.set_default_language(app.build_langs[0])
        xform.set_version(self.get_version())

    def render_xform(self):
        xform = XForm(self.source)
        self.add_stuff_to_xform(xform)
        return xform.render()

    def _get_active_actions(self, types):
        actions = {}
        for action_type in types:
            a = getattr(self.actions, action_type)
            if isinstance(a, list):
                if a:
                    actions[action_type] = a
            elif a.is_active():
                actions[action_type] = a
        return actions

    def active_actions(self):
        if self.get_app().application_version == '1.0':
            action_types = (
                'open_case', 'update_case', 'close_case',
                'open_referral', 'update_referral', 'close_referral',
                'case_preload', 'referral_preload'
            )
        else:
            if self.requires == 'none':
                action_types = (
                    'open_case', 'update_case', 'subcases',
                )
            elif self.requires == 'case':
                action_types = (
                    'update_case', 'close_case', 'case_preload', 'subcases',
                )
            else:
                # this is left around for legacy migrated apps
                action_types = (
                    'open_case', 'update_case', 'close_case',
                    'case_preload', 'subcases',
                )
        return self._get_active_actions(action_types)

    def active_non_preloader_actions(self):
        return self._get_active_actions((
            'open_case', 'update_case', 'close_case',
            'open_referral', 'update_referral', 'close_referral'))

    def get_questions(self, langs):
        return XForm(self.source).get_questions(langs)

    def export_json(self, dump_json=True):
        source = self.to_json()
        del source['unique_id']
        return json.dumps(source) if dump_json else source
    def rename_lang(self, old_lang, new_lang):
        _rename_key(self.name, old_lang, new_lang)
        try:
            self.rename_xform_language(old_lang, new_lang)
        except XFormError:
            pass

    def rename_xform_language(self, old_code, new_code):
        source = XForm(self.source)
        source.rename_language(old_code, new_code)
        source = source.render()
        self.source = source

    def check_actions(self):
        errors = []
        # reserved_words are hard-coded in three different places! Very lame of me
        # Here, case-config-ui-*.js, and module_view.html
        reserved_words = load_case_reserved_words()
        for key in self.actions.all_property_names():
            _, key = split_path(key)
            if key in reserved_words:
                errors.append({'type': 'update_case uses reserved word', 'word': key})
            # this regex is also copied in propertyList.ejs
            if not re.match(r'^[a-zA-Z][\w_-]*(/[a-zA-Z][\w_-]*)*$', key):
                errors.append({'type': 'update_case word illegal', 'word': key})

        for subcase_action in self.actions.subcases:
            if not subcase_action.case_type:
                errors.append({'type': 'subcase has no case type'})
            # no parent properties for subcase
            for key in subcase_action.case_properties:
                if not re.match(r'^[a-zA-Z][\w_-]*$', key):
                    errors.append({'type': 'update_case word illegal', 'word': key})

        if self.requires == 'none' and self.actions.open_case.is_active() \
                and not self.actions.open_case.name_path:
            errors.append({
                'type': 'case_name required',
                'message': ugettext(
                    'Every case must have a name. '
                    'Please specify a value for the name property under '
                    '"Save data to the following case properties"'
                )
            })

        try:
            valid_paths = set([question['value'] for question in self.get_questions(langs=[])])
        except XFormError as e:
            errors.append({'type': 'invalid xml', 'message': unicode(e)})
        else:
            paths = set()
            def generate_paths():
                for _, action in self.active_actions().items():
                    if isinstance(action, list):
                        actions = action
                    else:
                        actions = [action]
                    for action in actions:
                        if action.condition.type == 'if':
                            yield action.condition.question
                        if hasattr(action, 'name_path') and action.name_path:
                            yield action.name_path
                        if hasattr(action, 'case_name'):
                            yield action.case_name
                        if hasattr(action, 'external_id') and action.external_id:
                            yield action.external_id
                        if hasattr(action, 'update'):
                            for _, path in action.update.items():
                                yield path
                        if hasattr(action, 'case_properties'):
                            for _, path in action.case_properties.items():
                                yield path
                        if hasattr(action, 'preload'):
                            for path, _ in action.preload.items():
                                yield path
            paths.update(generate_paths())
            for path in paths:
                if path not in valid_paths:
                    errors.append({'type': 'path error', 'path': path})

        return errors

    def set_requires(self, requires):
        if requires == "none":
            self.actions.update_referral = DocumentSchema()
            self.actions.close_case = DocumentSchema()
            self.actions.close_referral = DocumentSchema()
            self.actions.case_preload = DocumentSchema()
            self.actions.referral_preload = DocumentSchema()
        elif requires == "case":
            self.actions.open_case = DocumentSchema()
            self.actions.close_referral= DocumentSchema()
            self.actions.update_referral = DocumentSchema()
            self.actions.referral_preload = DocumentSchema()
        elif requires == "referral":
            self.actions.open_case = DocumentSchema()
            self.actions.open_referral = DocumentSchema()

        self.requires = requires

    def requires_case(self):
        # all referrals also require cases
        return self.requires in ("case", "referral")

    def requires_case_type(self):
        return self.requires_case() or \
               bool(self.active_non_preloader_actions())

    def requires_referral(self):
        return self.requires == "referral"

class JRResourceProperty(StringProperty):
    def validate(self, value, required=True):
        super(JRResourceProperty, self).validate(value, required)
        if value is not None and not value.startswith('jr://'):
            raise BadValueError("JR Resources must start with 'jr://")
        return value
    
class NavMenuItemMediaMixin(DocumentSchema):
    media_image = JRResourceProperty(required=False)
    media_audio = JRResourceProperty(required=False)


class Form(FormBase, IndexedSchema, NavMenuItemMediaMixin):
    form_filter = StringProperty()

    def add_stuff_to_xform(self, xform):
        super(Form, self).add_stuff_to_xform(xform)
        xform.add_case_and_meta(self)

    def get_app(self):
        return self._parent._parent

    def get_module(self):
        return self._parent

    def all_other_forms_require_a_case(self):
        m = self.get_module()
        return all([form.requires == 'case' for form in m.get_forms() if form.id != self.id])

class UserRegistrationForm(FormBase):
    username_path = StringProperty(default='username')
    password_path = StringProperty(default='password')
    data_paths = DictProperty()

    def add_stuff_to_xform(self, xform):
        super(UserRegistrationForm, self).add_stuff_to_xform(xform)
        xform.add_user_registration(self.username_path, self.password_path, self.data_paths)

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
    header      = DictProperty()
    model       = StringProperty()
    field       = StringProperty()
    format      = StringProperty()

    enum        = DictProperty()
    late_flag   = IntegerProperty(default=30)
    advanced    = StringProperty(default="")
    filter_xpath = StringProperty(default="")
    time_ago_interval = FloatProperty(default=365.25)

    def rename_lang(self, old_lang, new_lang):
        for dct in (self.header, self.enum):
            _rename_key(dct, old_lang, new_lang)

    class TimeAgoInterval(object):
        map = {
            'day': 1.0,
            'week': 7.0,
            'month': 30.4375,
            'year': 365.25
        }
        @classmethod
        def get_from_old_format(cls, format):
            if format == 'years-ago':
                return cls.map['year']
            elif format == 'months-ago':
                return cls.map['month']

    @property
    def xpath(self):
        """
        Convert special names like date-opened to their casedb xpath equivalent (e.g. @date_opened).
        Only ever called by 2.0 apps.
        """
        parts = self.field.split('/')
        parts[-1] = CASE_PROPERTY_MAP.get(parts[-1], parts[-1])
        property = parts.pop()
        indexes = parts

        case = CaseXPath('')
        for index in indexes:
            case = case.index_id(index).case()
        return case.property(property)

    @classmethod
    def wrap(cls, data):
        if data.get('format') in ('months-ago', 'years-ago'):
            data['time_ago_interval'] = cls.TimeAgoInterval.get_from_old_format(data['format'])
            data['format'] = 'time-ago'
        return super(DetailColumn, cls).wrap(data)


class SortElement(IndexedSchema):
    field = StringProperty()
    type = StringProperty()
    direction = StringProperty()

    def values(self):
        values = {
            'field': self.field,
            'type': self.type,
            'direction': self.direction,
        }

        return values


class Detail(IndexedSchema):
    """
    Full configuration for a case selection screen

    """
    type = StringProperty(choices=DETAIL_TYPES)

    columns = SchemaListProperty(DetailColumn)
    get_columns = IndexedSchema.Getter('columns')

    sort_elements = SchemaListProperty(SortElement)

    @parse_int([1])
    def get_column(self, i):
        return self.columns[i].with_id(i%len(self.columns), self)

    def append_column(self, column):
        self.columns.append(column)

    def update_column(self, column_id, column):
        my_column = self.columns[column_id]

        my_column.model = column.model
        my_column.field = column.field
        my_column.format = column.format
        my_column.late_flag = column.late_flag
        my_column.advanced = column.advanced

        for lang in column.header:
            my_column.header[lang] = column.header[lang]

        for key in column.enum:
            for lang in column.enum[key]:
                if key not in my_column.enum:
                    my_column.enum[key] = {}
                my_column.enum[key][lang] = column.enum[key][lang]

    def delete_column(self, column_id):
        del self.columns[column_id]

    def rename_lang(self, old_lang, new_lang):
        for column in self.columns:
            column.rename_lang(old_lang, new_lang)

    @property
    def display(self):
        return "short" if self.type.endswith('short') else 'long'


    def filter_xpath(self):

        filters = []
        for i,column in enumerate(self.columns):
            if column.format == 'filter':
                filters.append("(%s)" % column.filter_xpath.replace('.', '%s_%s_%s' % (column.model, column.field, i + 1)))
        xpath = ' and '.join(filters)
        return partial_escape(xpath)

class CaseList(IndexedSchema):
    label = DictProperty()
    show = BooleanProperty(default=False)

    def rename_lang(self, old_lang, new_lang):
        for dct in (self.label,):
            _rename_key(dct, old_lang, new_lang)

class Module(IndexedSchema, NavMenuItemMediaMixin):
    """
    A group of related forms, and configuration that applies to them all.
    Translates to a top-level menu on the phone.

    """
    name = DictProperty()
    case_label = DictProperty()
    referral_label = DictProperty()
    forms = SchemaListProperty(Form)
    details = SchemaListProperty(Detail)
    case_type = StringProperty()
    put_in_root = BooleanProperty(default=False)
    case_list = SchemaProperty(CaseList)
    referral_list = SchemaProperty(CaseList)
    task_list = SchemaProperty(CaseList)

    def rename_lang(self, old_lang, new_lang):
        _rename_key(self.name, old_lang, new_lang)
        for form in self.get_forms():
            form.rename_lang(old_lang, new_lang)
        for detail in self.details:
            detail.rename_lang(old_lang, new_lang)
        for case_list in (self.case_list, self.referral_list):
            case_list.rename_lang(old_lang, new_lang)

    get_forms = IndexedSchema.Getter('forms')
    @parse_int([1])
    def get_form(self, i):
        self__forms = self.forms
        return self__forms[i].with_id(i%len(self.forms), self)

    get_details = IndexedSchema.Getter('details')

    def get_detail(self, detail_type):
        for detail in self.get_details():
            if detail.type == detail_type:
                return detail
        raise Exception("Module %s has no detail type %s" % (self, detail_type))

    @property
    def detail_sort_elements(self):
        try:
            return self.get_detail('case_short').sort_elements
        except Exception:
            return []

    def export_json(self, dump_json=True, keep_unique_id=False):
        source = self.to_json()
        if not keep_unique_id:
            for form in source['forms']:
                del form['unique_id']
        return json.dumps(source) if dump_json else source

    def export_jvalue(self):
        return self.export_json(dump_json=False, keep_unique_id=True)
    
    def requires(self):
        r = set(["none"])
        for form in self.get_forms():
            r.add(form.requires)
        if self.case_list.show:
            r.add('case')
        if self.referral_list.show:
            r.add('referral')
        for val in ("referral", "case", "none"):
            if val in r:
                return val
    def detail_types(self):
        return {
            "referral": ["case_short", "case_long", "ref_short", "ref_long"],
            "case": ["case_short", "case_long"],
            "none": []
        }[self.requires()]
    def requires_case_details(self):
        ret = False
        if self.case_list.show:
            return True
        for form in self.get_forms():
            if form.requires_case():
                ret = True
                break
        return ret

    @memoized
    def all_forms_require_a_case(self):
        return all([form.requires == 'case' for form in self.get_forms()])

class VersioningError(Exception):
    """For errors that violate the principals of versioning in VersionedDoc"""
    pass


class VersionedDoc(LazyAttachmentDoc):
    """
    A document that keeps an auto-incrementing version number, knows how to make copies of itself,
    delete a copy of itself, and revert back to an earlier copy of itself.

    """
    domain = StringProperty()
    copy_of = StringProperty()
    version = IntegerProperty()
    short_url = StringProperty()
    short_odk_url = StringProperty()

    _meta_fields = ['_id', '_rev', 'domain', 'copy_of', 'version', 'short_url', 'short_odk_url']

    @property
    def id(self):
        return self._id

    def save(self, response_json=None, increment_version=None, **params):
        if increment_version is None:
            increment_version = not self.copy_of
        if increment_version:
            self.version = self.version + 1 if self.version else 1
        super(VersionedDoc, self).save(**params)
        if response_json is not None:
            if 'update' not in response_json:
                response_json['update'] = {}
            response_json['update']['app-version'] = self.version

    def make_build(self):
        assert self.get_id
        assert self.copy_of is None
        cls = self.__class__
        copies = cls.view('app_manager/applications', key=[self.domain, self._id, self.version], include_docs=True, limit=1).all()
        if copies:
            copy = copies[0]
        else:
            copy = deepcopy(self.to_json())
            bad_keys = ('_id', '_rev', '_attachments',
                        'short_url', 'short_odk_url', 'recipients')

            for bad_key in bad_keys:
                if bad_key in copy:
                    del copy[bad_key]

            copy = cls.wrap(copy)
            copy['copy_of'] = self._id

            copy.copy_attachments(self)
        return copy

    def copy_attachments(self, other, regexp=ATTACHMENT_REGEX):
        for name in other.lazy_list_attachments() or {}:
            if regexp is None or re.match(regexp, name):
                self.lazy_put_attachment(other.lazy_fetch_attachment(name), name)

    def make_reversion_to_copy(self, copy):
        """
        Replaces couch doc with a copy of the backup ("copy").
        Returns the another Application/RemoteApp referring to this
        updated couch doc. The returned doc should be used in place of
        the original doc, i.e. should be called as follows:
            app = app.make_reversion_to_copy(copy)
            app.save()
        """
        if copy.copy_of != self._id:
            raise VersioningError("%s is not a copy of %s" % (copy, self))
        app = deepcopy(copy.to_json())
        app['_rev'] = self._rev
        app['_id'] = self._id
        app['version'] = self.version
        app['copy_of'] = None
        if '_attachments' in app:
            del app['_attachments']
        cls = self.__class__
        app = cls.wrap(app)
        app.copy_attachments(copy)
        return app

    def delete_copy(self, copy):
        if copy.copy_of != self._id:
            raise VersioningError("%s is not a copy of %s" % (copy, self))
        copy.delete_app()
        copy.save(increment_version=False)

    def scrub_source(self, source):
        """
        To be overridden.

        Use this to scrub out anything
        that should be shown in the
        application source, such as ids, etc.

        """
        raise NotImplemented()

    def export_json(self, dump_json=True):
        source = deepcopy(self.to_json())
        for field in self._meta_fields:
            if field in source:
                del source[field]
        _attachments = {}
        for name in source.get('_attachments', {}):
            if re.match(ATTACHMENT_REGEX, name):
                _attachments[name] = self.fetch_attachment(name)
        source['_attachments'] = _attachments
        self.scrub_source(source)

        return json.dumps(source) if dump_json else source
    @classmethod
    def from_source(cls, source, domain):
        for field in cls._meta_fields:
            if field in source:
                del source[field]
        source['domain'] = domain
        app = cls.wrap(source)
        return app

    def is_deleted(self):
        return self.doc_type.endswith(DELETED_SUFFIX)

    def unretire(self):
        self.doc_type = self.get_doc_type()
        self.save()

    def get_doc_type(self):
        if self.doc_type.endswith(DELETED_SUFFIX):
            return self.doc_type[:-len(DELETED_SUFFIX)]
        else:
            return self.doc_type


def absolute_url_property(method):
    """
    Helper for the various fully qualified application URLs
    Turns a method returning an unqualified URL
    into a property returning a fully qualified URL
    (e.g., '/my_url/' => 'https://www.commcarehq.org/my_url/')
    Expects `self.url_base` to be fully qualified url base

    """
    @wraps(method)
    def _inner(self):
        return "%s%s" % (self.url_base, method(self))
    return property(_inner)

class ApplicationBase(VersionedDoc, SnapshotMixin):
    """
    Abstract base class for Application and RemoteApp.
    Contains methods for generating the various files and zipping them into CommCare.jar

    """

    recipients = StringProperty(default="")

    # this is the supported way of specifying which commcare build to use
    build_spec = SchemaProperty(BuildSpec)
    platform = StringProperty(
        choices=["nokia/s40", "nokia/s60", "winmo", "generic"],
        default="nokia/s40"
    )
    text_input = StringProperty(
        choices=['roman', 'native', 'custom-keys', 'qwerty'],
        default="roman"
    )
    success_message = DictProperty()

    # The following properties should only appear on saved builds
    # built_with stores a record of CommCare build used in a saved app
    built_with = SchemaProperty(BuildRecord)
    build_signed = BooleanProperty(default=True)
    built_on = DateTimeProperty(required=False)
    build_comment = StringProperty()
    comment_from = StringProperty()

    # watch out for a past bug:
    # when reverting to a build that happens to be released
    # that got copied into into the new app doc, and when new releases were made,
    # they were automatically starred
    # AFAIK this is fixed in code, but my rear its ugly head in an as-yet-not-understood
    # way for apps that already had this problem. Just keep an eye out
    is_released = BooleanProperty(default=False)

    # django-style salted hash of the admin password
    admin_password = StringProperty()
    # a=Alphanumeric, n=Numeric, x=Neither (not allowed)
    admin_password_charset = StringProperty(choices=['a', 'n', 'x'], default='n')

    # This is here instead of in Application because it needs to be available in stub representation
    application_version = StringProperty(default=APP_V1, choices=[APP_V1, APP_V2], required=False)

    langs = StringListProperty()
    # only the languages that go in the build
    build_langs = StringListProperty()

    # exchange properties
    cached_properties = DictProperty()
    description = StringProperty()
    deployment_date = DateTimeProperty()
    phone_model = StringProperty()
    user_type = StringProperty()
    attribution_notes = StringProperty()

    # always false for RemoteApp
    case_sharing = BooleanProperty(default=False)

    @classmethod
    def wrap(cls, data):
        # scrape for old conventions and get rid of them
        if data.has_key("commcare_build"):
            version, build_number = data['commcare_build'].split('/')
            data['build_spec'] = BuildSpec.from_string("%s/latest" % version).to_json()
            del data['commcare_build']
        if data.has_key("commcare_tag"):
            version, build_number = current_builds.TAG_MAP[data['commcare_tag']]
            data['build_spec'] = BuildSpec.from_string("%s/latest" % version).to_json()
            del data['commcare_tag']
        if data.has_key("built_with") and isinstance(data['built_with'], basestring):
            data['built_with'] = BuildSpec.from_string(data['built_with']).to_json()

        if data.has_key('native_input'):
            if not data.has_key('text_input'):
                data['text_input'] = 'native' if data['native_input'] else 'roman'
            del data['native_input']

        should_save = False
        if data.has_key('original_doc'):
            data['copy_history'] = [data.pop('original_doc')]
            should_save = True

        # if description is empty, replace it with the short description if it exists
        data["description"] = data.get("description", None) or data.get("short_description", None)

        self = super(ApplicationBase, cls).wrap(data)
        if not self.build_spec or self.build_spec.is_null():
            self.build_spec = CommCareBuildConfig.fetch().get_default(self.application_version)

        if should_save:
            self.save()
        return self

    @classmethod
    def by_domain(cls, domain):
        return cls.view('app_manager/applications_brief',
                        startkey=[domain],
                        endkey=[domain, {}],
                        include_docs=True,
                        stale=settings.COUCH_STALE_QUERY).all()

    def rename_lang(self, old_lang, new_lang):
        validate_lang(new_lang)

    def is_remote_app(self):
        return False

    def get_latest_app(self, released_only=True):
        if released_only:
            return get_app(self.domain, self.get_id, latest=True)
        else:
            return self.view('app_manager/applications',
                startkey=[self.domain, self.get_id, {}],
                endkey=[self.domain, self.get_id],
                include_docs=True,
                limit=1,
                descending=True,
            ).first()


    def get_latest_saved(self):
        """
        This looks really similar to get_latest_app, not sure why tim added
        """
        if not hasattr(self, '_latest_saved'):
            released = self.__class__.view('app_manager/applications',
                startkey=['^ReleasedApplications', self.domain, self._id, {}],
                endkey=['^ReleasedApplications', self.domain, self._id],
                limit=1,
                descending=True,
                include_docs=True
            )
            if len(released) > 0:
                self._latest_saved = released.all()[0]
            else:
                saved = self.__class__.view('app_manager/saved_app',
                    startkey=[self.domain, self._id, {}],
                    endkey=[self.domain, self._id],
                    descending=True,
                    limit=1,
                    include_docs=True
                )
                if len(saved) > 0:
                    self._latest_saved = saved.all()[0]
                else:
                    self._latest_saved = None # do not return this app!
        return self._latest_saved

    def set_admin_password(self, raw_password):
        import random
        algo = 'sha1'
        salt = get_hexdigest(algo, str(random.random()), str(random.random()))[:5]
        hsh = get_hexdigest(algo, salt, raw_password)
        self.admin_password = '%s$%s$%s' % (algo, salt, hsh)

        if raw_password.isnumeric():
            self.admin_password_charset = 'n'
        elif raw_password.isalnum():
            self.admin_password_charset = 'a'
        else:
            self.admin_password_charset = 'x'

    def check_password_charset(self):
        errors = []
        if hasattr(self, 'profile'):
            password_format = self.profile.get('properties', {}).get('password_format', 'n')
            message = 'Your app requires {0} passwords but the admin password is not {0}'

            if password_format == 'n' and self.admin_password_charset in 'ax':
                errors.append({'type': 'password_format', 'message': message.format('numeric')})
            if password_format == 'a' and self.admin_password_charset in 'x':
                errors.append({'type': 'password_format', 'message': message.format('alphanumeric')})
        return errors

    def get_build(self):
#        version, build_number = current_builds.TAG_MAP[self.commcare_tag]
#        return CommCareBuild.get_build(version, build_number)
        return self.build_spec.get_build()

    def get_preview_build(self):
        preview = self.get_build()

        for path in getattr(preview, '_attachments', {}):
            if path.startswith('Generic/WebDemo'):
                return preview
        return CommCareBuildConfig.fetch().preview.get_build()

    @property
    def commcare_minor_release(self):
        """This is mostly just for views"""
        return self.build_spec.minor_release()

    def get_build_label(self):
        """This is a helper to look up a human readable name for a build tag"""
#        for option in current_builds.MENU_OPTIONS:
#            if option['tag'] == self.commcare_tag:
#                return option['label']
        for item in CommCareBuildConfig.fetch().menu:
            if item['build'].to_string() == self.build_spec.to_string():
                return item['label']
        return self.build_spec.get_label()

    @property
    def short_name(self):
        return self.name if len(self.name) <= 12 else '%s..' % self.name[:10]

    @property
    def url_base(self):
        return get_url_base()

    @absolute_url_property
    def post_url(self):
        return reverse('receiver_post_with_app_id', args=[self.domain, self.copy_of or self.get_id])

    @absolute_url_property
    def key_server_url(self):
        return reverse('key_server_url', args=[self.domain])

    @absolute_url_property
    def ota_restore_url(self):
        return reverse('corehq.apps.ota.views.restore', args=[self.domain])

    @absolute_url_property
    def form_record_url(self):
        return '/a/%s/api/custom/pact_formdata/v1/' % self.domain

    @absolute_url_property
    def hq_profile_url(self):
        return "%s?latest=true" % (
            reverse('download_profile', args=[self.domain, self._id])
        )
    @property
    def profile_loc(self):
        return "jr://resource/profile.xml"

    @absolute_url_property
    def jar_url(self):
        return reverse('corehq.apps.app_manager.views.download_jar', args=[self.domain, self._id])

    def get_jar_path(self):

        spec = {
            'nokia/s40': 'Nokia/S40',
            'nokia/s60': 'Nokia/S60',
            'generic': 'Generic/Default',
            'winmo': 'Native/WinMo'
        }[self.platform]

        if self.platform in ('nokia/s40', 'nokia/s60'):
            spec += {
                ('native',): '-native-input',
                ('roman',): '-generic',
                ('custom-keys',):  '-custom-keys',
                ('qwerty',): '-qwerty'
            }[(self.text_input,)]

        return spec

    def get_jadjar(self):
        return self.get_build().get_jadjar(self.get_jar_path())

    def validate_jar_path(self):
        build = self.get_build()
        setting = commcare_settings.SETTINGS_LOOKUP['hq']['text_input']
        value = self.text_input
        setting_version = setting['since'].get(value)

        if setting_version:
            setting_version = tuple(map(int, setting_version.split('.')))
            my_version = build.minor_release()

            if my_version < setting_version:
                i = setting['values'].index(value)
                assert i != -1
                name = _(setting['value_names'][i])
                raise AppError(
                    '%s Text Input is not supported '
                    'in CommCare versions before %s.%s. '
                    '(You are using %s.%s)'
                ) % ((name,) + setting_version + my_version)


    @property
    def jad_settings(self):
        return {
            'JavaRosa-Admin-Password': self.admin_password,
            'Profile': self.profile_loc,
            'MIDlet-Jar-URL': self.jar_url,
            #'MIDlet-Name': self.name,
            # e.g. 2011-Apr-11 20:45
            'CommCare-Release': "true",
            'Build-Number': self.version,
        }

    def create_jadjar(self, save=False):
        try:
            return (
                self.lazy_fetch_attachment('CommCare.jad'),
                self.lazy_fetch_attachment('CommCare.jar'),
            )
        except (ResourceError, KeyError):
            built_on = datetime.utcnow()
            all_files = self.create_all_files()
            jad_settings = {
                'Released-on': built_on.strftime("%Y-%b-%d %H:%M"),
            }
            jad_settings.update(self.jad_settings)
            jadjar = self.get_jadjar().pack(all_files, jad_settings)
            if save:
                self.built_on = built_on
                self.built_with = BuildRecord(
                    version=jadjar.version,
                    build_number=jadjar.build_number,
                    signed=jadjar.signed,
                    datetime=built_on,
                )

                self.lazy_put_attachment(jadjar.jad, 'CommCare.jad')
                self.lazy_put_attachment(jadjar.jar, 'CommCare.jar')

                for filepath in all_files:
                    self.lazy_put_attachment(all_files[filepath],
                                             'files/%s' % filepath)

            return jadjar.jad, jadjar.jar

    def validate_app(self):
        errors = []

        errors.extend(self.check_password_charset())

        try:
            self.validate_jar_path()
            self.create_all_files()
        except (AppError, XFormValidationError, XFormError) as e:
            errors.append({'type': 'error', 'message': unicode(e)})
        except Exception as e:
            if settings.DEBUG:
                raise
            logging.exception('Unexpected error building app')
            errors.append({'type': 'error', 'message': 'unexpected error: %s' % e})
        return errors

    @absolute_url_property
    def odk_profile_url(self):
        return reverse('corehq.apps.app_manager.views.download_odk_profile', args=[self.domain, self._id])

    @property
    def odk_profile_display_url(self):
        return self.short_odk_url or self.odk_profile_url

    def get_odk_qr_code(self):
        """Returns a QR code, as a PNG to install on CC-ODK"""
        try:
            return self.lazy_fetch_attachment("qrcode.png")
        except ResourceNotFound:
            try:
                from pygooglechart import QRChart
            except ImportError:
                raise Exception(MISSING_DEPENDECY)
            HEIGHT = WIDTH = 250
            code = QRChart(HEIGHT, WIDTH)
            code.add_data(self.odk_profile_url)

            # "Level H" error correction with a 0 pixel margin
            code.set_ec('H', 0)
            f, fname = tempfile.mkstemp()
            code.download(fname)
            os.close(f)
            with open(fname, "rb") as f:
                png_data = f.read()
                self.lazy_put_attachment(png_data, "qrcode.png",
                                         content_type="image/png")
            return png_data

    def fetch_jar(self):
        return self.get_jadjar().fetch_jar()

    def fetch_emulator_commcare_jar(self):
        path = "Generic/WebDemo"
        jadjar = self.get_preview_build().get_jadjar(path)
        jadjar = jadjar.pack(self.create_all_files())
        return jadjar.jar

    def make_build(self, comment=None, user_id=None, previous_version=None):
        copy = super(ApplicationBase, self).make_build()
        if not copy._id:
            # I expect this always to be the case
            # but check explicitly so as not to change the _id if it exists
            copy._id = copy.get_db().server.next_uuid()

        copy.set_form_versions(previous_version)
        copy.create_jadjar(save=True)

        try:
            # since this hard to put in a test
            # I'm putting this assert here if copy._id is ever None
            # which makes tests error
            assert copy._id
            copy.short_url = bitly.shorten(
                get_url_base() + reverse('corehq.apps.app_manager.views.download_jad', args=[copy.domain, copy._id])
            )
            copy.short_odk_url = bitly.shorten(
                get_url_base() + reverse('corehq.apps.app_manager.views.download_odk_profile', args=[copy.domain, copy._id])
            )
        except AssertionError:
            raise
        except:        # URLError, BitlyError
            # for offline only
            logging.exception("Problem creating bitly url for app %s. Do you have network?" % self.get_id)
            copy.short_url = None
            copy.short_odk_url = None

        copy.build_comment = comment
        copy.comment_from = user_id
        copy.is_released = False

        return copy

    def delete_app(self):
        self.doc_type += '-Deleted'
        record = DeleteApplicationRecord(
            domain=self.domain,
            app_id=self.id,
            datetime=datetime.utcnow()
        )
        record.save()
        return record

    def set_form_versions(self, previous_version):
        # by default doing nothing here is fine.
        pass

#class Profile(DocumentSchema):
#    features = DictProperty()
#    properties = DictProperty()

def validate_lang(lang):
    if not re.match(r'^[a-z]{2,3}(-[a-z]*)?$', lang):
        raise ValueError("Invalid Language")

class SavedAppBuild(ApplicationBase):
    def to_saved_build_json(self, timezone):
        data = super(SavedAppBuild, self).to_json().copy()
        data.update({
            'id': self.id,
            'built_on_date': utc_to_timezone(data['built_on'], timezone, "%b %d, %Y"),
            'built_on_time': utc_to_timezone(data['built_on'], timezone, "%H:%M %Z"),
            'build_label': self.built_with.get_label(),
            'jar_path': self.get_jar_path(),
            'short_name': self.short_name
        })
        if data['comment_from']:
            comment_user = CouchUser.get(data['comment_from'])
            data['comment_user_name'] = comment_user.full_name

        return data


class Application(ApplicationBase, TranslationMixin, HQMediaMixin):
    """
    An Application that can be created entirely through the online interface

    """
    user_registration = SchemaProperty(UserRegistrationForm)
    show_user_registration = BooleanProperty(default=False, required=True)
    modules = SchemaListProperty(Module)
    name = StringProperty()
    profile = DictProperty() #SchemaProperty(Profile)
    use_custom_suite = BooleanProperty(default=False)
    force_http = BooleanProperty(default=False)
    cloudcare_enabled = BooleanProperty(default=False)
    include_media_resources = BooleanProperty(default=False)

    @classmethod
    def wrap(cls, data):
        for module in data.get('modules', []):
            for attr in ('case_label', 'referral_label'):
                if not module.has_key(attr):
                    module[attr] = {}
            for lang in data['langs']:
                if not module['case_label'].get(lang):
                    module['case_label'][lang] = commcare_translations.load_translations(lang).get('cchq.case', 'Cases')
                if not module['referral_label'].get(lang):
                    module['referral_label'][lang] = commcare_translations.load_translations(lang).get('cchq.referral', 'Referrals')
        if not data.get('build_langs'):
            data['build_langs'] = data['langs']
        return super(Application, cls).wrap(data)

    def save(self, *args, **kwargs):
        super(Application, self).save(*args, **kwargs)
        from corehq.apps.app_manager import signals # Import loop if this is imported at the top; TODO: revamp so signal_connections <- models <- signals
        signals.app_post_save.send(Application, application=self)

    def make_reversion_to_copy(self, copy):
        app = super(Application, self).make_reversion_to_copy(copy)

        for form in app.get_forms():
            # reset the form's validation cache, since the form content is
            # likely to have changed in the revert!
            form.validation_cache = None

        return app


    @property
    def profile_url(self):
        return self.hq_profile_url

    @property
    def url_base(self):
        # force_http is a deprecated hack
        # for safety we're just special-casing the only
        # domain that ever used it, wvmoz
        if self.force_http and self.domain == 'wvmoz':
            return settings.INSECURE_URL_BASE
        else:
            return get_url_base()

    @absolute_url_property
    def suite_url(self):
        return reverse('download_suite', args=[self.domain, self.get_id])

    @property
    def suite_loc(self):
        return "suite.xml"

    @absolute_url_property
    def media_suite_url(self):
        return reverse('download_media_suite', args=[self.domain, self.get_id])

    @property
    def media_suite_loc(self):
        return "media_suite.xml"

    @property
    def enable_multi_sort(self):
        """
        Multi (tiered) sort is supported by apps version 2.2 or higher
        """
        try:
            return self.get_build().minor_release() >= (2, 2)
        except KeyError:
            # if for some reason there is no build number it's probably
            # old or bugged
            return False

    @property
    def default_language(self):
        return self.build_langs[0] if len(self.build_langs) > 0 else "en"

    def fetch_xform(self, module_id=None, form_id=None, form=None):
        if not form:
            form = self.get_module(module_id).get_form(form_id)
        return form.validate_form().render_xform().encode('utf-8')

    def set_form_versions(self, previous_version):
        # this will make builds slower, but they're async now so hopefully
        # that's fine.

        def _hash(val):
            return hashlib.md5(val).hexdigest()

        if previous_version:
            for form_stuff in self.get_forms(bare=False):
                filename = 'files/%s' % self.get_form_filename(**form_stuff)
                form = form_stuff["form"]
                try:
                    previous_form = previous_version.get_form(form.unique_id)
                    # we don't want to perform any validation on previous_form
                    # because it could have been built with an eariler version
                    # of commcarehq in which there was a bug
                    # that let invalid forms through
                    previous_source = previous_version.fetch_attachment(filename)
                except (ResourceNotFound, KeyError):
                    # if this is a new form just use my version
                    form.version = self.version
                else:
                    previous_hash = _hash(previous_source)

                    # hack - temporarily set my version to the previous version
                    # so that that's not treated as the diff
                    form.version = previous_form.get_version()
                    my_hash = _hash(self.fetch_xform(form=form))
                    if previous_hash != my_hash:
                        form.version = self.version

    def _create_custom_app_strings(self, lang):
        def trans(d):
            return clean_trans(d, langs)
        id_strings = IdStrings()
        langs = [lang] + self.langs
        yield id_strings.homescreen_title(), self.name
        yield id_strings.app_display_name(), self.name
        for module in self.get_modules():
            for detail in module.get_details():
                if detail.type.startswith('case'):
                    label = trans(module.case_label)
                else:
                    label = trans(module.referral_label)
                yield id_strings.detail_title_locale(module, detail), label
                for column in detail.get_columns():
                    yield id_strings.detail_column_header_locale(module, detail, column), trans(column.header)
                    if column.format == 'enum':
                        for key, val in column.enum.items():
                            yield id_strings.detail_column_enum_variable(module, detail, column, key), trans(val)
            yield id_strings.module_locale(module), trans(module.name)
            if module.case_list.show:
                yield id_strings.case_list_locale(module), trans(module.case_list.label) or "Case List"
            if module.referral_list.show:
                yield id_strings.referral_list_locale(module), trans(module.referral_list.label)
            for form in module.get_forms():
                yield id_strings.form_locale(form), trans(form.name) + ('${0}' if form.show_count else '')

    def create_app_strings(self, lang, include_blank_custom=False):
        def non_empty_only(dct):
            return dict([(key, value) for key, value in dct.items() if value])
        if lang != "default":
            messages = {"cchq.case": "Case", "cchq.referral": "Referral"}

            custom = dict(self._create_custom_app_strings(lang))
            if include_blank_custom:
                messages.update(custom)
            else:
                messages.update(non_empty_only(custom))

            # include language code names
            for lc in self.langs:
                name = langcodes.get_name(lc) or lc
                if name:
                    messages[lc] = name

            cc_trans = commcare_translations.load_translations(lang)
            messages.update(cc_trans)

            messages.update(non_empty_only(self.translations.get(lang, {})))
        else:
            messages = {}
            for lc in reversed(self.langs):
                if lc == "default":
                    continue
                new_messages = commcare_translations.loads(
                    self.create_app_strings(lc, include_blank_custom=True)
                )

                for key, val in new_messages.items():
                    # do not overwrite a real trans with a blank trans
                    if not (val == '' and key in messages):
                        messages[key] = val
        return commcare_translations.dumps(messages).encode('utf-8')

    @property
    def skip_validation(self):
        properties = (self.profile or {}).get('properties', {})
        return properties.get('cc-content-valid', 'yes')

    @property
    def jad_settings(self):
        s = super(Application, self).jad_settings
        s.update({
            'Skip-Validation': self.skip_validation,
        })
        return s

    def create_profile(self, is_odk=False, template='app_manager/profile.xml'):
        app_profile = defaultdict(dict)
        app_profile.update(self.profile)
        # the following code is to let HQ override CommCare defaults
        # impetus: Weekly Logging should be Short (HQ override) instead of Never (CommCare default)
        # setting.default is assumed to also be the CommCare default unless there's a setting.commcare_default
        for setting in commcare_settings.SETTINGS:
            type = setting['type']
            if type in ('properties', 'features') and setting['id'] not in app_profile[type]:
                if 'commcare_default' in setting and setting['commcare_default'] != setting['default']:
                    app_profile[type][setting['id']] = setting['default']

        if self.case_sharing:
            app_profile['properties']['server-tether'] = 'sync'

        return render_to_string(template, {
            'is_odk': is_odk,
            'app': self,
            'profile_url': self.profile_url if not is_odk else (self.odk_profile_url + '?latest=true'),
            'app_profile': app_profile,
            'suite_url': self.suite_url,
            'suite_loc': self.suite_loc,
            'post_url': self.post_url,
            'key_server_url': self.key_server_url,
            'post_test_url': self.post_url,
            'ota_restore_url': self.ota_restore_url,
            'cc_user_domain': cc_user_domain(self.domain)
        }).decode('utf-8')

    @property
    def custom_suite(self):
        try:
            return self.fetch_attachment('custom_suite.xml')
        except Exception:
            return ""

    def set_custom_suite(self, value):
        self.put_attachment(value, 'custom_suite.xml')

    def create_suite(self):
        if self.application_version == '1.0':
            template='app_manager/suite-%s.xml' % self.application_version
            return render_to_string(template, {
                'app': self,
                'langs': ["default"] + self.build_langs
            })
        else:
            return suite_xml.SuiteGenerator(self).generate_suite()

    def create_media_suite(self):
        return suite_xml.SuiteGenerator(self).generate_suite(
            sections=['media_resources']
        )

    @classmethod
    def get_form_filename(cls, type=None, form=None, module=None):
        if type == 'user_registration':
            return 'user_registration.xml'
        else:
            return 'modules-%s/forms-%s.xml' % (module.id, form.id)

    def create_all_files(self):
        files = {
            'profile.xml': self.create_profile(is_odk=False),
            'profile.ccpr': self.create_profile(is_odk=True),
            'suite.xml': self.create_suite(),
        }
        if self.include_media_resources:
            files['media_suite.xml'] = self.create_media_suite()

        for lang in ['default'] + self.build_langs:
            files["%s/app_strings.txt" % lang] = self.create_app_strings(lang)
        for form_stuff in self.get_forms(bare=False):
            filename = self.get_form_filename(**form_stuff)
            form = form_stuff['form']
            files[filename] = self.fetch_xform(form=form)
        return files

    get_modules = IndexedSchema.Getter('modules')

    @parse_int([1])
    def get_module(self, i):
        self__modules = self.modules
        return self__modules[i].with_id(i%len(self__modules), self)

    def get_user_registration(self):
        form = self.user_registration
        form._app = self
        if not form.source:
            form.source = load_default_user_registration().format(user_registration_xmlns="%s%s" % (
                get_url_base(),
                reverse('view_user_registration', args=[self.domain, self.id]),
            ))
        return form

    def get_forms(self, bare=True):
        if self.show_user_registration:
            yield self.get_user_registration() if bare else {
                'type': 'user_registration',
                'form': self.get_user_registration()
            }
        for module in self.get_modules():
            for form in module.get_forms():
                yield form if bare else {
                    'type': 'module_form',
                    'module': module,
                    'form': form
                }

    def get_form(self, unique_form_id, bare=True):
        def matches(form):
            return form.get_unique_id() == unique_form_id
        for obj in self.get_forms(bare):
            if matches(obj if bare else obj['form']):
                return obj
        raise KeyError("Form in app '%s' with unique id '%s' not found" % (self.id, unique_form_id))

    @classmethod
    def new_app(cls, domain, name, application_version, lang="en"):
        app = cls(domain=domain, modules=[], name=name, langs=[lang], build_langs=[lang], application_version=application_version)
        return app

    def new_module(self, name, lang):
        self.modules.append(
            Module(
                name={lang if lang else "en": name if name else "Untitled Module"},
                forms=[],
                case_type='',
                details=[Detail(type=detail_type, columns=[]) for detail_type in DETAIL_TYPES],
            )
        )
        return self.get_module(-1)

    def new_module_from_source(self, source):
        self.modules.append(Module.wrap(source))
        return self.get_module(-1)

    @parse_int([1])
    def delete_module(self, module_id):
        module = self.modules[module_id]
        record = DeleteModuleRecord(
            domain=self.domain,
            app_id=self.id,
            module_id=module_id,
            module=module,
            datetime=datetime.utcnow()
        )
        del self.modules[module_id]
        record.save()
        return record

    def new_form(self, module_id, name, lang, attachment=""):
        module = self.get_module(module_id)
        form = Form(
            name={lang if lang else "en": name if name else "Untitled Form"},
        )
        module.forms.append(form)
        form = module.get_form(-1)
        form.source = attachment
        return form

    def new_form_from_source(self, module_id, source):
        module = self.get_module(module_id)
        module.forms.append(Form.wrap(source))
        form = module.get_form(-1)
        return form
    @parse_int([1, 2])
    def delete_form(self, module_id, form_id):
        module = self.get_module(module_id)
        form = module['forms'][form_id]
        record = DeleteFormRecord(
            domain=self.domain,
            app_id=self.id,
            module_id=module_id,
            form_id=form_id,
            form=form,
            datetime=datetime.utcnow()
        )
        record.save()
        del module['forms'][form_id]
        return record

    def rename_lang(self, old_lang, new_lang):
        validate_lang(new_lang)
        if old_lang == new_lang:
            return
        if new_lang in self.langs:
            raise AppError("Language %s already exists!" % new_lang)
        for i,lang in enumerate(self.langs):
            if lang == old_lang:
                self.langs[i] = new_lang
        for module in self.get_modules():
            module.rename_lang(old_lang, new_lang)
        _rename_key(self.translations, old_lang, new_lang)


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
    def rearrange_forms(self, to_module_id, from_module_id, i, j):
        forms = self.modules[to_module_id]['forms']
        forms.insert(i, forms.pop(j) if to_module_id == from_module_id else self.modules[from_module_id]['forms'].pop(j))
        self.modules[to_module_id]['forms'] = forms
        if self.modules[to_module_id]['case_type'] != self.modules[from_module_id]['case_type']:
            return 'case type conflict'
    def scrub_source(self, source):
        def change_unique_id(form):
            unique_id = form['unique_id']
            new_unique_id = FormBase.generate_id()
            form['unique_id'] = new_unique_id
            if source['_attachments'].has_key("%s.xml" % unique_id):
                source['_attachments']["%s.xml" % new_unique_id] = source['_attachments'].pop("%s.xml" % unique_id)

        change_unique_id(source['user_registration'])
        for m,module in enumerate(source['modules']):
            for f,form in enumerate(module['forms']):
                change_unique_id(source['modules'][m]['forms'][f])

    def copy_form(self, module_id, form_id, to_module_id):
        form  = self.get_module(module_id).get_form(form_id)
        copy_source = deepcopy(form.to_json())
        if copy_source.has_key('unique_id'):
            del copy_source['unique_id']

        copy_form = self.new_form_from_source(to_module_id, copy_source)

        def xmlname(aform):
            return "%s.xml" % aform.get_unique_id()

        save_xform(self, copy_form, form.source)

        if self.modules[module_id]['case_type'] != self.modules[to_module_id]['case_type']:
            return 'case type conflict'

    @cached_property
    def has_case_management(self):
        for module in self.get_modules():
            for form in module.get_forms():
                if len(form.active_actions()) > 0:
                    return True
        return False

    def has_media(self):
        return len(self.multimedia_map) > 0

    @memoized
    def get_xmlns_map(self):
        xmlns_map = defaultdict(list)
        for form in self.get_forms():
            xmlns_map[form.xmlns].append(form)
        return xmlns_map

    def get_questions(self, xmlns):
        forms = self.get_xmlns_map()[xmlns]
        if len(forms) != 1:
            logging.error('App %s in domain %s has %s forms with xmlns %s' % (
                self.get_id,
                self.domain,
                len(forms),
                xmlns,
            ))
            return []
        else:
            form, = forms
        return form.get_questions(self.langs)

    def validate_app(self):
        xmlns_count = defaultdict(int)
        errors = []

        for lang in self.langs:
            if not lang:
                errors.append({'type': 'empty lang'})

        if not self.modules:
            errors.append({'type': "no modules"})
        for module in self.get_modules():
            if not module.forms:
                errors.append({
                    'type': 'no forms',
                    'module': build_error_utils.get_module_info(module),
                })
            if module.case_list.show:
                errors.extend(
                    build_error_utils.get_case_errors(
                        module,
                        needs_case_type=True,
                        needs_case_detail=True
                    )
                )


        for form in self.get_forms():
            errors.extend(form.validate_for_build())

            # make sure that there aren't duplicate xmlns's
            xmlns_count[form.xmlns] += 1
            for xmlns in xmlns_count:
                if xmlns_count[xmlns] > 1:
                    errors.append({'type': "duplicate xmlns", "xmlns": xmlns})

        if not errors:
            errors = super(Application, self).validate_app()
        return errors

    @classmethod
    def get_by_xmlns(cls, domain, xmlns):
        r = get_db().view('exports_forms/by_xmlns', key=[domain, {}, xmlns], group=True).one()
        return cls.get(r['value']['app']['id']) if r and 'app' in r['value'] else None


class RemoteApp(ApplicationBase):
    """
    A wrapper for a url pointing to a suite or profile file. This allows you to
    write all the files for an app by hand, and then give the url to app_manager
    and let it package everything together for you.

    """
    profile_url = StringProperty(default="http://")
    name = StringProperty()
    manage_urls = BooleanProperty(default=False)

    questions_map = DictProperty(required=False)

    def is_remote_app(self):
        return True

    @classmethod
    def new_app(cls, domain, name, lang='en'):
        app = cls(domain=domain, name=name, langs=[lang])
        return app

    def create_profile(self, is_odk=False):
        # we don't do odk for now anyway
        try:
            profile = urlopen(self.profile_url).read()
        except Exception:
            raise AppError('Unable to access profile url: "%s"' % self.profile_url)

        if self.manage_urls or self.build_langs:
            profile_xml = WrappedNode(profile)

            def set_property(key, value):
                node = profile_xml.find('property[@key="%s"]' % key)

                if node.xml is None:
                    from lxml import etree as ET
                    node = ET.Element('property')
                    profile_xml.xml.insert(0, node)
                    node.attrib['key'] = key

                node.attrib['value'] = value

            def set_attribute(key, value):
                profile_xml.attrib[key] = value

            def reset_suite_remote_url():
                suite_local_text = profile_xml.findtext('suite/resource/location[@authority="local"]')
                suite_remote = profile_xml.find('suite/resource/location[@authority="remote"]')
                suite_name = self.strip_location(suite_local_text)
                suite_remote.xml.text = self.url_base + urljoin(reverse('download_index', args=[self.domain, self.get_id]), suite_name)

            if self.manage_urls:
                set_attribute('update', self.hq_profile_url)
                set_property("ota-restore-url", self.ota_restore_url)
                set_property("PostURL", self.post_url)
                set_property("cc_user_domain", cc_user_domain(self.domain))
                set_property('form-record-url', self.form_record_url)
                set_property('key_server', self.key_server_url)
                reset_suite_remote_url()

            if self.build_langs:
                set_property("cur_locale", self.build_langs[0])

            profile = profile_xml.render()
        return profile

    def strip_location(self, location):
        base = '/'.join(self.profile_url.split('/')[:-1]) + '/'

        def strip_left(prefix):
            string = location
            if string.startswith(prefix):
                return string[len(prefix):]

        return strip_left('./') or strip_left(base) or strip_left('jr://resource/') or location

    def fetch_file(self, location):
        location = self.strip_location(location)
        url = urljoin(self.profile_url, location)

        try:
            content = urlopen(url).read()
        except Exception:
            raise AppError('Unable to access resource url: "%s"' % url)

        return location, content

    @classmethod
    def get_locations(cls, suite):
        for resource in suite.findall('*/resource'):
            try:
                loc = resource.findtext('location[@authority="local"]')
            except Exception:
                loc = resource.findtext('location[@authority="remote"]')
            yield resource.getparent().tag, loc

    @property
    def SUITE_XPATH(self):
        return 'suite/resource/location[@authority="local"]'

    def create_all_files(self):
        files = {
            'profile.xml': self.create_profile(),
        }
        tree = _parse_xml(files['profile.xml'])

        def add_file_from_path(path, strict=False):
            try:
                loc = tree.find(path).text
            except (TypeError, AttributeError):
                if strict:
                    raise AppError("problem with file path reference!")
                else:
                    return
            loc, file = self.fetch_file(loc)
            files[loc] = file
            return loc, file

        add_file_from_path('features/users/logo')
        try:
            _, suite = add_file_from_path(self.SUITE_XPATH, strict=True)
        except AppError:
            raise AppError(ugettext('Problem loading suite file from profile file. Is your profile file correct?'))

        suite_xml = _parse_xml(suite)

        for tag, location in self.get_locations(suite_xml):
            location, data = self.fetch_file(location)
            if tag == 'xform' and self.build_langs:
                try:
                    xform = XForm(data)
                except XFormError as e:
                    raise XFormError('In file %s: %s' % (location, e))
                xform.exclude_languages(whitelist=self.build_langs)
                data = xform.render()
            files.update({location: data})
        return files

    def scrub_source(self, source):
        pass

    def make_questions_map(self):
        if self.copy_of:
            xmlns_map = {}

            def fetch(location):
                filepath = self.strip_location(location)
                return self.fetch_attachment('files/%s' % filepath)

            profile_xml = _parse_xml(fetch('profile.xml'))
            suite_location = profile_xml.find(self.SUITE_XPATH).text
            suite_xml = _parse_xml(fetch(suite_location))

            for tag, location in self.get_locations(suite_xml):
                if tag == 'xform':
                    xform = XForm(fetch(location))
                    xmlns = xform.data_node.tag_xmlns
                    questions = xform.get_questions(self.build_langs)
                    xmlns_map[xmlns] = questions
            return xmlns_map
        else:
            return None

    def get_questions(self, xmlns):
        if not self.questions_map:
            self.questions_map = self.make_questions_map()
            self.save()
        questions = self.questions_map.get(xmlns, [])
        return questions



class DomainError(Exception):
    pass

class AppError(Exception):
    pass

def get_app(domain, app_id, wrap_cls=None, latest=False):
    """
    Utility for getting an app, making sure it's in the domain specified, and wrapping it in the right class
    (Application or RemoteApp).

    """

    if latest:
        try:
            original_app = get_db().get(app_id)
        except ResourceNotFound:
            raise Http404
        if not domain:
            try:
                domain = original_app['domain']
            except Exception:
                raise Http404

        if original_app.get('copy_of'):
            parent_app_id = original_app.get('copy_of')
            min_version = original_app['version']
        else:
            parent_app_id = original_app['_id']
            min_version = -1

        latest_app = get_db().view('app_manager/applications',
            startkey=['^ReleasedApplications', domain, parent_app_id, {}],
            endkey=['^ReleasedApplications', domain, parent_app_id, min_version],
            limit=1,
            descending=True,
            include_docs=True
        ).one()
        try:
            app = latest_app['doc']
        except TypeError:
            # If no starred builds, return act as if latest=False
            app = original_app
    else:
        try:
            app = get_db().get(app_id)
        except Exception:
            raise Http404
    if domain and app['domain'] != domain:
        raise Http404
    cls = wrap_cls or {
        'Application': Application,
        'Application-Deleted': Application,
        "RemoteApp": RemoteApp,
        "RemoteApp-Deleted": RemoteApp,
    }[app['doc_type']]
    app = cls.wrap(app)
    return app

EXAMPLE_DOMAIN = 'example'
BUG_REPORTS_DOMAIN = 'bug-reports'

def _get_or_create_app(app_id):
    if app_id == "example--hello-world":
        try:
            app = Application.get(app_id)
        except ResourceNotFound:
            app = Application.wrap(fixtures.hello_world_example)
            app._id = app_id
            app.domain = EXAMPLE_DOMAIN
            app.save()
            return _get_or_create_app(app_id)
        return app
    else:
        return get_app(None, app_id)

str_to_cls = {
    "Application": Application,
    "Application-Deleted": Application,
    "RemoteApp": RemoteApp,
    "RemoteApp-Deleted": RemoteApp,
}

def import_app(app_id_or_source, domain, name=None, validate_source_domain=None):
    if isinstance(app_id_or_source, basestring):
        app_id = app_id_or_source
        source = _get_or_create_app(app_id)
        src_dom = source['domain']
        if validate_source_domain:
            validate_source_domain(src_dom)
        source = source.export_json()
        source = json.loads(source)
    else:
        source = app_id_or_source
    try:
        attachments = source['_attachments']
    except KeyError:
        attachments = {}
    finally:
        source['_attachments'] = {}
    if name:
        source['name'] = name
    cls = str_to_cls[source['doc_type']]
    app = cls.from_source(source, domain)
    app.save()
    for name, attachment in attachments.items():
        if re.match(ATTACHMENT_REGEX, name):
            app.put_attachment(attachment, name)
    return app

class DeleteApplicationRecord(DeleteRecord):
    app_id = StringProperty()

    def undo(self):
        app = ApplicationBase.get(self.app_id)
        app.doc_type = app.get_doc_type()
        app.save(increment_version=False)

class DeleteModuleRecord(DeleteRecord):
    app_id = StringProperty()
    module_id = IntegerProperty()
    module = SchemaProperty(Module)

    def undo(self):
        app = Application.get(self.app_id)
        modules = app.modules
        modules.insert(self.module_id, self.module)
        app.modules = modules
        app.save()

class DeleteFormRecord(DeleteRecord):
    app_id = StringProperty()
    module_id = IntegerProperty()
    form_id = IntegerProperty()
    form = SchemaProperty(Form)

    def undo(self):
        app = Application.get(self.app_id)
        forms = app.modules[self.module_id].forms
        forms.insert(self.form_id, self.form)
        app.modules[self.module_id].forms = forms
        app.save()

Form.get_command_id = lambda self: "m{module.id}-f{form.id}".format(module=self.get_module(), form=self)
Form.get_locale_id = lambda self: "forms.m{module.id}f{form.id}".format(module=self.get_module(), form=self)

Module.get_locale_id = lambda self: "modules.m{module.id}".format(module=self)

Module.get_case_list_command_id = lambda self: "m{module.id}-case-list".format(module=self)
Module.get_case_list_locale_id = lambda self: "case_lists.m{module.id}".format(module=self)

Module.get_referral_list_command_id = lambda self: "m{module.id}-referral-list".format(module=self)
Module.get_referral_list_locale_id = lambda self: "referral_lists.m{module.id}".format(module=self)
import corehq.apps.app_manager.signals

@register_repeater_type
class AppStructureRepeater(Repeater):
    def get_payload(self, repeat_record):
        return repeat_record.payload_id # This is the id of the application, currently all we forward
