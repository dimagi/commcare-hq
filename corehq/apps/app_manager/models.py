# coding=utf-8
from distutils.version import LooseVersion
from itertools import chain
import tempfile
import os
import logging
import hashlib
import random
import json
import types
import re
from collections import defaultdict
from datetime import datetime
from functools import wraps
from copy import deepcopy
from urllib2 import urlopen
from urlparse import urljoin

from couchdbkit import ResourceConflict, MultipleResultsFound
import itertools
from lxml import etree
from django.core.cache import cache
from django.utils.encoding import force_unicode
from django.utils.safestring import mark_safe
from django.utils.translation import override, ugettext as _, ugettext
from couchdbkit.exceptions import BadValueError, DocTypeError
from dimagi.ext.couchdbkit import *
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import Http404
from django.template.loader import render_to_string
from restkit.errors import ResourceError
from couchdbkit.resource import ResourceNotFound
from corehq import toggles, privileges
from corehq.const import USER_DATE_FORMAT, USER_TIME_FORMAT
from corehq.apps.app_manager.feature_support import CommCareFeatureSupportMixin
from corehq.util.quickcache import quickcache
from corehq.util.timezones.conversions import ServerTime
from dimagi.utils.couch.bulk import get_docs
from django_prbac.exceptions import PermissionDenied
from corehq.apps.accounting.utils import domain_has_privilege

from corehq.apps.app_manager.commcare_settings import check_condition
from corehq.apps.app_manager.const import *
from corehq.apps.app_manager.xpath import dot_interpolate, LocationXpath
from corehq.apps.builds import get_default_build_spec
from corehq.util.hash_compat import make_password
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.couch.lazy_attachment_doc import LazyAttachmentDoc
from dimagi.utils.couch.undo import DeleteRecord, DELETED_SUFFIX
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import get_url_base, parse_int
from dimagi.utils.couch.database import get_db
import commcare_translations
from corehq.util import bitly
from corehq.util import view_utils
from corehq.apps.appstore.models import SnapshotMixin
from corehq.apps.builds.models import BuildSpec, CommCareBuildConfig, BuildRecord
from corehq.apps.hqmedia.models import HQMediaMixin
from corehq.apps.translations.models import TranslationMixin
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import cc_user_domain
from corehq.apps.domain.models import cached_property, Domain
from corehq.apps.app_manager import current_builds, app_strings, remote_app
from corehq.apps.app_manager import suite_xml, commcare_settings
from corehq.apps.app_manager.util import (
    split_path,
    save_xform,
    get_correct_app_class,
    ParentCasePropertyBuilder,
    is_usercase_in_use)
from corehq.apps.app_manager.xform import XForm, parse_xml as _parse_xml, \
    validate_xform
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from .exceptions import (
    AppEditingError,
    BlankXFormError,
    ConflictingCaseTypeError,
    FormNotFoundException,
    IncompatibleFormTypeException,
    LocationXpathValidationError,
    ModuleNotFoundException,
    ModuleIdMissingException,
    RearrangeError,
    VersioningError,
    XFormException,
    XFormIdNotUnique,
    XFormValidationError,
)
from corehq.apps.app_manager import id_strings
from jsonpath_rw import jsonpath, parse

WORKFLOW_DEFAULT = 'default'
WORKFLOW_ROOT = 'root'
WORKFLOW_MODULE = 'module'
WORKFLOW_PREVIOUS = 'previous_screen'
WORKFLOW_FORM = 'form'

DETAIL_TYPES = ['case_short', 'case_long', 'ref_short', 'ref_long']

FIELD_SEPARATOR = ':'

ATTACHMENT_REGEX = r'[^/]*\.xml'

ANDROID_LOGO_PROPERTY_MAPPING = {
    'hq_logo_android_home': 'brand-banner-home',
    'hq_logo_android_login': 'brand-banner-login',
}


def jsonpath_update(datum_context, value):
    field = datum_context.path.fields[0]
    parent = jsonpath.Parent().find(datum_context)[0]
    parent.value[field] = value

# store a list of references to form ID's so that
# when an app is copied we can update the references
# with the new values
form_id_references = []


def FormIdProperty(expression, **kwargs):
    """
    Create a StringProperty that references a form ID. This is necessary because
    form IDs change when apps are copied so we need to make sure we update
    any references to the them.
    :param expression:  jsonpath expression that can be used to find the field
    :param kwargs:      arguments to be passed to the underlying StringProperty
    """
    path_expression = parse(expression)
    assert isinstance(path_expression, jsonpath.Child), "only child path expressions are supported"
    field = path_expression.right
    assert len(field.fields) == 1, 'path expression can only reference a single field'

    form_id_references.append(path_expression)
    return StringProperty(**kwargs)


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
def load_form_template(filename):
    with open(os.path.join(os.path.dirname(__file__), 'data', filename)) as f:
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
    type = StringProperty(choices=["if", "always", "never"], default="never")
    question = StringProperty()
    answer = StringProperty()
    operator = StringProperty(choices=['=', 'selected'], default='=')

    def is_active(self):
        return self.type in ('if', 'always')

class FormAction(DocumentSchema):
    """
    Corresponds to Case XML

    """
    condition = SchemaProperty(FormActionCondition)

    def is_active(self):
        return self.condition.is_active()

    @classmethod
    def get_action_paths(cls, action):
        if action.condition.type == 'if':
            yield action.condition.question

        for __, path in cls.get_action_properties(action):
            yield path

    @classmethod
    def get_action_properties(self, action):
        action_properties = action.properties()
        if 'name_path' in action_properties and action.name_path:
            yield 'name', action.name_path
        if 'case_name' in action_properties:
            yield 'name', action.case_name
        if 'external_id' in action_properties and action.external_id:
            yield 'external_id', action.external_id
        if 'update' in action_properties:
            for name, path in action.update.items():
                yield name, path
        if 'case_properties' in action_properties:
            for name, path in action.case_properties.items():
                yield name, path
        if 'preload' in action_properties:
            for path, name in action.preload.items():
                yield name, path


class UpdateCaseAction(FormAction):

    update = DictProperty()


class PreloadAction(FormAction):

    preload = DictProperty()

    def is_active(self):
        return bool(self.preload)


class UpdateReferralAction(FormAction):

    followup_date = StringProperty()

    def get_followup_date(self):
        if self.followup_date:
            return "if(date({followup_date}) >= date(today()), {followup_date}, date(today() + 2))".format(
                followup_date=self.followup_date,
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
    reference_id = StringProperty()
    case_properties = DictProperty()
    repeat_context = StringProperty()

    close_condition = SchemaProperty(FormActionCondition)

class FormActions(DocumentSchema):

    open_case = SchemaProperty(OpenCaseAction)
    update_case = SchemaProperty(UpdateCaseAction)
    close_case = SchemaProperty(FormAction)
    open_referral = SchemaProperty(OpenReferralAction)
    update_referral = SchemaProperty(UpdateReferralAction)
    close_referral = SchemaProperty(FormAction)

    case_preload = SchemaProperty(PreloadAction)
    referral_preload = SchemaProperty(PreloadAction)

    usercase_update = SchemaProperty(UpdateCaseAction)
    usercase_preload = SchemaProperty(PreloadAction)

    subcases = SchemaListProperty(OpenSubCaseAction)

    def all_property_names(self):
        names = set()
        names.update(self.update_case.update.keys())
        names.update(self.case_preload.preload.values())
        for subcase in self.subcases:
            names.update(subcase.case_properties.keys())
        return names


class AdvancedAction(IndexedSchema):
    case_type = StringProperty()
    case_tag = StringProperty()
    case_properties = DictProperty()
    parent_tag = StringProperty()
    parent_reference_id = StringProperty(default='parent')

    close_condition = SchemaProperty(FormActionCondition)

    __eq__ = DocumentSchema.__eq__

    def get_paths(self):
        for path in self.case_properties.values():
            yield path

        if self.close_condition.type == 'if':
            yield self.close_condition.question

    def get_property_names(self):
        return set(self.case_properties.keys())

    @property
    def is_subcase(self):
        return self.parent_tag


class AutoSelectCase(DocumentSchema):
    """
    Configuration for auto-selecting a case.
    Attributes:
        value_source    Reference to the source of the value. For mode = fixture,
                        this represents the FixtureDataType ID. For mode = case
                        this represents the 'case_tag' for the case.
                        The modes 'user' and 'raw' don't require a value_source.
        value_key       The actual field that contains the case ID. Can be a case
                        index or a user data key or a fixture field name or the raw
                        xpath expression.

    """
    mode = StringProperty(choices=[AUTO_SELECT_USER,
                                   AUTO_SELECT_FIXTURE,
                                   AUTO_SELECT_CASE,
                                   AUTO_SELECT_USERCASE,
                                   AUTO_SELECT_RAW])
    value_source = StringProperty()
    value_key = StringProperty(required=True)


class LoadUpdateAction(AdvancedAction):
    """
    details_module:     Use the case list configuration from this module to show the cases.
    preload:            Value from the case to load into the form. Keys are question paths, values are case properties.
    auto_select:        Configuration for auto-selecting the case
    show_product_stock: If True list the product stock using the module's Product List configuration.
    product_program:    Only show products for this CommCare Supply program.
    """
    details_module = StringProperty()
    preload = DictProperty()
    auto_select = SchemaProperty(AutoSelectCase, default=None)
    show_product_stock = BooleanProperty(default=False)
    product_program = StringProperty()

    def get_paths(self):
        for path in super(LoadUpdateAction, self).get_paths():
            yield path

        for path in self.preload.keys():
            yield path

    def get_property_names(self):
        names = super(LoadUpdateAction, self).get_property_names()
        names.update(self.preload.values())
        return names

    @property
    def case_session_var(self):
        return 'case_id_{0}'.format(self.case_tag)


class AdvancedOpenCaseAction(AdvancedAction):
    name_path = StringProperty()
    repeat_context = StringProperty()

    open_condition = SchemaProperty(FormActionCondition)

    def get_paths(self):
        for path in super(AdvancedOpenCaseAction, self).get_paths():
            yield path

        yield self.name_path

        if self.open_condition.type == 'if':
            yield self.open_condition.question

    @property
    def case_session_var(self):
        return 'case_id_new_{}_{}'.format(self.case_type, self.id)


class AdvancedFormActions(DocumentSchema):
    load_update_cases = SchemaListProperty(LoadUpdateAction)
    open_cases = SchemaListProperty(AdvancedOpenCaseAction)

    get_load_update_actions = IndexedSchema.Getter('load_update_cases')
    get_open_actions = IndexedSchema.Getter('open_cases')

    def get_all_actions(self):
        return itertools.chain(self.get_load_update_actions(), self.get_open_actions())

    def get_subcase_actions(self):
        return (a for a in self.get_all_actions() if a.parent_tag)

    def get_open_subcase_actions(self, parent_case_type=None):
        for action in [a for a in self.open_cases if a.parent_tag]:
            if not parent_case_type:
                yield action
            else:
                parent = self.actions_meta_by_tag[action.parent_tag]['action']
                if parent.case_type == parent_case_type:
                    yield action

    def get_case_tags(self):
        for action in self.get_all_actions():
            yield action.case_tag

    def get_action_from_tag(self, tag):
        return self.actions_meta_by_tag.get(tag, {}).get('action', None)

    @property
    def actions_meta_by_tag(self):
        return self._action_meta()['by_tag']

    @property
    def actions_meta_by_parent_tag(self):
        return self._action_meta()['by_parent_tag']

    def get_action_hierarchy(self, action):
        current = action
        hierarchy = [current]
        while current and current.parent_tag:
            parent = self.get_action_from_tag(current.parent_tag)
            current = parent
            if parent:
                if parent in hierarchy:
                    circular = [a.case_tag for a in hierarchy + [parent]]
                    raise ValueError("Circular reference in subcase hierarchy: {0}".format(circular))
                hierarchy.append(parent)

        return hierarchy

    @property
    def auto_select_actions(self):
        return self._action_meta()['by_auto_select_mode']

    @memoized
    def _action_meta(self):
        meta = {
            'by_tag': {},
            'by_parent_tag': {},
            'by_auto_select_mode': {
                AUTO_SELECT_USER: [],
                AUTO_SELECT_CASE: [],
                AUTO_SELECT_FIXTURE: [],
                AUTO_SELECT_USERCASE: [],
                AUTO_SELECT_RAW: [],
            }
        }

        def add_actions(type, action_list):
            for action in action_list:
                meta['by_tag'][action.case_tag] = {
                    'type': type,
                    'action': action
                }
                if action.parent_tag:
                    meta['by_parent_tag'][action.parent_tag] = {
                        'type': type,
                        'action': action
                    }
                if type == 'load' and action.auto_select and action.auto_select.mode:
                    meta['by_auto_select_mode'][action.auto_select.mode].append(action)

        add_actions('load', self.get_load_update_actions())
        add_actions('open', self.get_open_actions())

        return meta

class FormSource(object):
    def __get__(self, form, form_cls):
        if not form:
            return self
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
        except ResourceNotFound:
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
        cache.set(key, value, 7*24*60*60)  # cache for 7 days


class ScheduleVisit(DocumentSchema):
    """
    due:         Days after the anchor date that this visit is due
    late_window: Days after the due day that this visit is valid until
    """
    due = IntegerProperty()
    late_window = IntegerProperty()


class FormLink(DocumentSchema):
    """
    xpath:      xpath condition that must be true in order to open next form
    form_id:    id of next form to open
    """
    xpath = StringProperty()
    form_id = FormIdProperty('modules[*].forms[*].form_links[*].form_id')


class FormSchedule(DocumentSchema):
    """
    anchor:                     Case property containing a date after which this schedule becomes active
    expiry:                     Days after the anchor date that this schedule expires (optional)
    visit_list:                 List of visits in this schedule
    post_schedule_increment:    Repeat period for visits to occur after the last fixed visit (optional)
    transition_condition:       Condition under which the schedule transitions to the next phase
    termination_condition:      Condition under which the schedule terminates
    """
    anchor = StringProperty()
    expires = IntegerProperty()
    visits = SchemaListProperty(ScheduleVisit)
    post_schedule_increment = IntegerProperty()
    transition_condition = SchemaProperty(FormActionCondition)
    termination_condition = SchemaProperty(FormActionCondition)


class FormBase(DocumentSchema):
    """
    Part of a Managed Application; configuration for a form.
    Translates to a second-level menu on the phone

    """
    form_type = None

    name = DictProperty(unicode)
    unique_id = StringProperty()
    show_count = BooleanProperty(default=False)
    xmlns = StringProperty()
    version = IntegerProperty()
    source = FormSource()
    validation_cache = CachedStringProperty(
        lambda self: "cache-%s-%s-validation" % (self.get_app().get_id, self.unique_id)
    )
    post_form_workflow = StringProperty(
        default=WORKFLOW_DEFAULT,
        choices=[WORKFLOW_DEFAULT, WORKFLOW_ROOT, WORKFLOW_MODULE, WORKFLOW_PREVIOUS, WORKFLOW_FORM]
    )
    auto_gps_capture = BooleanProperty(default=False)
    no_vellum = BooleanProperty(default=False)
    form_links = SchemaListProperty(FormLink)

    @classmethod
    def wrap(cls, data):
        data.pop('validation_cache', '')

        if cls is FormBase:
            doc_type = data['doc_type']
            if doc_type == 'Form':
                return Form.wrap(data)
            elif doc_type == 'AdvancedForm':
                return AdvancedForm.wrap(data)
            else:
                try:
                    return CareplanForm.wrap(data)
                except ValueError:
                    raise ValueError('Unexpected doc_type for Form', doc_type)
        else:
            return super(FormBase, cls).wrap(data)

    @classmethod
    def generate_id(cls):
        return hex(random.getrandbits(160))[2:-1]

    @classmethod
    def get_form(cls, form_unique_id, and_app=False):
        try:
            d = get_db().view(
                'app_manager/xforms_index',
                key=form_unique_id
            ).one()
        except MultipleResultsFound as e:
            raise XFormIdNotUnique(
                "xform id '%s' not unique: %s" % (form_unique_id, e)
            )
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

    @property
    def schedule_form_id(self):
        return self.unique_id[:6]

    def wrapped_xform(self):
        return XForm(self.source)

    def validate_form(self):
        vc = self.validation_cache
        if vc is None:
            try:
                validate_xform(self.source,
                               version=self.get_app().application_version)
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

    def validate_for_build(self, validate_module=True):
        errors = []

        try:
            module = self.get_module()
        except AttributeError:
            module = None

        meta = {
            'form_type': self.form_type,
            'module': module.get_module_info() if module else {},
            'form': {"id": self.id if hasattr(self, 'id') else None, "name": self.name}
        }

        xml_valid = False
        if self.source == '':
            errors.append(dict(type="blank form", **meta))
        else:
            try:
                _parse_xml(self.source)
                xml_valid = True
            except XFormException as e:
                errors.append(dict(
                    type="invalid xml",
                    message=unicode(e) if self.source else '',
                    **meta
                ))
            except ValueError:
                logging.error("Failed: _parse_xml(string=%r)" % self.source)
                raise
            else:
                try:
                    self.validate_form()
                except XFormValidationError as e:
                    error = {'type': 'validation error', 'validation_message': unicode(e)}
                    error.update(meta)
                    errors.append(error)

        try:
            self.case_list_module
        except AssertionError:
            msg = _("Form referenced as the registration form for multiple modules.")
            error = {'type': 'validation error', 'validation_message': msg}
            error.update(meta)
            errors.append(error)

        if self.post_form_workflow == WORKFLOW_FORM and not self.form_links:
            errors.append(dict(type="no form links", **meta))

        errors.extend(self.extended_build_validation(meta, xml_valid, validate_module))

        return errors

    def extended_build_validation(self, error_meta, xml_valid, validate_module=True):
        """
        Override to perform additional validation during build process.
        """
        return []

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

    def get_version(self):
        return self.version if self.version else self.get_app().version

    def add_stuff_to_xform(self, xform):
        app = self.get_app()
        xform.exclude_languages(app.build_langs)
        xform.set_default_language(app.build_langs[0])
        xform.normalize_itext()
        xform.strip_vellum_ns_attributes()
        xform.set_version(self.get_version())

    def render_xform(self):
        xform = XForm(self.source)
        self.add_stuff_to_xform(xform)
        return xform.render()

    @quickcache(['self.source', 'langs', 'include_triggers', 'include_groups', 'include_translations'])
    def get_questions(self, langs, include_triggers=False,
                      include_groups=False, include_translations=False):
        return XForm(self.source).get_questions(
            langs=langs,
            include_triggers=include_triggers,
            include_groups=include_groups,
            include_translations=include_translations,
        )

    @memoized
    def get_case_property_name_formatter(self):
        """Get a function that formats case property names

        The returned function requires two arguments
        `(case_property_name, data_path)` and returns a string.
        """
        try:
            valid_paths = {question['value']: question['tag']
                           for question in self.get_questions(langs=[])}
        except XFormException as e:
            # punt on invalid xml (sorry, no rich attachments)
            valid_paths = {}
        def format_key(key, path):
            if valid_paths.get(path) == "upload":
                return u"{}{}".format(ATTACHMENT_PREFIX, key)
            return key
        return format_key

    def export_json(self, dump_json=True):
        source = self.to_json()
        del source['unique_id']
        return json.dumps(source) if dump_json else source

    def rename_lang(self, old_lang, new_lang):
        _rename_key(self.name, old_lang, new_lang)
        try:
            self.rename_xform_language(old_lang, new_lang)
        except XFormException:
            pass

    def rename_xform_language(self, old_code, new_code):
        source = XForm(self.source)
        if source.exists():
            source.rename_language(old_code, new_code)
            source = source.render()
            self.source = source

    def default_name(self):
        app = self.get_app()
        return trans(
            self.name,
            [app.default_language] + app.build_langs,
            include_lang=False
        )

    @property
    def full_path_name(self):
        return "%(app_name)s > %(module_name)s > %(form_name)s" % {
            'app_name': self.get_app().name,
            'module_name': self.get_module().default_name(),
            'form_name': self.default_name()
        }

    @property
    def has_fixtures(self):
        return 'src="jr://fixture/item-list:' in self.source

    def get_auto_gps_capture(self):
        app = self.get_app()
        if app.build_version and app.enable_auto_gps:
            return self.auto_gps_capture or app.auto_gps_capture
        else:
            return False

    def is_registration_form(self, case_type=None):
        """
        Should return True if this form passes the following tests:
         * does not require a case
         * registers a case of type 'case_type' if supplied
        """
        raise NotImplementedError()
    
    def update_app_case_meta(self, app_case_meta):
        pass

    @property
    @memoized
    def case_list_module(self):
        case_list_modules = [
            mod for mod in self.get_app().get_modules() if mod.case_list_form.form_id == self.unique_id
        ]
        assert len(case_list_modules) <= 1, "Form referenced my multiple modules"
        return case_list_modules[0] if case_list_modules else None

    @property
    def is_case_list_form(self):
        return self.case_list_module is not None


class IndexedFormBase(FormBase, IndexedSchema):
    def get_app(self):
        return self._parent._parent

    def get_module(self):
        return self._parent

    def get_case_type(self):
        return self._parent.case_type

    def check_case_properties(self, all_names=None, subcase_names=None, case_tag=None):
        all_names = all_names or []
        subcase_names = subcase_names or []
        errors = []

        # reserved_words are hard-coded in three different places!
        # Here, case-config-ui-*.js, and module_view.html
        reserved_words = load_case_reserved_words()
        for key in all_names:
            try:
                validate_property(key)
            except ValueError:
                errors.append({'type': 'update_case word illegal', 'word': key, 'case_tag': case_tag})
            _, key = split_path(key)
            if key in reserved_words:
                errors.append({'type': 'update_case uses reserved word', 'word': key, 'case_tag': case_tag})

        # no parent properties for subcase
        for key in subcase_names:
            if not re.match(r'^[a-zA-Z][\w_-]*$', key):
                errors.append({'type': 'update_case word illegal', 'word': key, 'case_tag': case_tag})

        return errors

    def check_paths(self, paths):
        errors = []
        try:
            valid_paths = {question['value']: question['tag']
                           for question in self.get_questions(langs=[])}
        except XFormException as e:
            errors.append({'type': 'invalid xml', 'message': unicode(e)})
        else:
            no_multimedia = not self.get_app().enable_multimedia_case_property
            for path in set(paths):
                if path not in valid_paths:
                    errors.append({'type': 'path error', 'path': path})
                elif no_multimedia and valid_paths[path] == "upload":
                    errors.append({'type': 'multimedia case property not supported', 'path': path})

        return errors

    def add_property_save(self, app_case_meta, case_type, name,
                          questions, question_path, condition=None):
        if question_path in questions:
            app_case_meta.add_property_save(
                case_type,
                name,
                self.unique_id,
                questions[question_path],
                condition
            )
        else:
            app_case_meta.add_property_error(
                case_type,
                name,
                self.unique_id,
                "%s is not a valid question" % question_path
            )

    def add_property_load(self, app_case_meta, case_type, name,
                          questions, question_path):
        if question_path in questions:
            app_case_meta.add_property_load(
                case_type,
                name,
                self.unique_id,
                questions[question_path]
            )
        else:
            app_case_meta.add_property_error(
                case_type,
                name,
                self.unique_id,
                "%s is not a valid question" % question_path
            )


class JRResourceProperty(StringProperty):

    def validate(self, value, required=True):
        super(JRResourceProperty, self).validate(value, required)
        if value is not None and not value.startswith('jr://'):
            raise BadValueError("JR Resources must start with 'jr://")
        return value


class NavMenuItemMediaMixin(DocumentSchema):

    media_image = JRResourceProperty(required=False)
    media_audio = JRResourceProperty(required=False)


class Form(IndexedFormBase, NavMenuItemMediaMixin):
    form_type = 'module_form'

    form_filter = StringProperty()
    requires = StringProperty(choices=["case", "referral", "none"], default="none")
    actions = SchemaProperty(FormActions)

    def add_stuff_to_xform(self, xform):
        super(Form, self).add_stuff_to_xform(xform)
        xform.add_case_and_meta(self)

    def all_other_forms_require_a_case(self):
        m = self.get_module()
        return all([form.requires == 'case' for form in m.get_forms() if form.id != self.id])

    def session_var_for_action(self, action_type, subcase_index=None):
        module_case_type = self.get_module().case_type
        if action_type == 'open_case':
            return 'case_id_new_{}_0'.format(module_case_type)
        if action_type == 'subcases':
            opens_case = 'open_case' in self.active_actions()
            subcase_type = self.actions.subcases[subcase_index].case_type
            if opens_case:
                subcase_index += 1
            return 'case_id_new_{}_{}'.format(subcase_type, subcase_index)

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
        if self.get_app().application_version == APP_V1:
            action_types = (
                'open_case', 'update_case', 'close_case',
                'open_referral', 'update_referral', 'close_referral',
                'case_preload', 'referral_preload'
            )
        else:
            if self.requires == 'none':
                action_types = (
                    'open_case', 'update_case', 'close_case', 'subcases',
                    'usercase_update', 'usercase_preload',
                )
            elif self.requires == 'case':
                action_types = (
                    'update_case', 'close_case', 'case_preload', 'subcases',
                    'usercase_update', 'usercase_preload',
                )
            else:
                # this is left around for legacy migrated apps
                action_types = (
                    'open_case', 'update_case', 'close_case',
                    'case_preload', 'subcases',
                    'usercase_update', 'usercase_preload',
                )
        return self._get_active_actions(action_types)

    def active_non_preloader_actions(self):
        return self._get_active_actions((
            'open_case', 'update_case', 'close_case',
            'open_referral', 'update_referral', 'close_referral'))

    def check_actions(self):
        errors = []

        subcase_names = set()
        for subcase_action in self.actions.subcases:
            if not subcase_action.case_type:
                errors.append({'type': 'subcase has no case type'})

            subcase_names.update(subcase_action.case_properties)

        if self.requires == 'none' and self.actions.open_case.is_active() \
                and not self.actions.open_case.name_path:
            errors.append({'type': 'case_name required'})

        errors.extend(self.check_case_properties(
            all_names=self.actions.all_property_names(),
            subcase_names=subcase_names
        ))

        def generate_paths():
            for action in self.active_actions().values():
                if isinstance(action, list):
                    actions = action
                else:
                    actions = [action]
                for action in actions:
                    for path in FormAction.get_action_paths(action):
                        yield path

        errors.extend(self.check_paths(generate_paths()))

        return errors

    def requires_case(self):
        # all referrals also require cases
        return self.requires in ("case", "referral")

    def requires_case_type(self):
        return self.requires_case() or \
            bool(self.active_non_preloader_actions())

    def requires_referral(self):
        return self.requires == "referral"

    def is_registration_form(self, case_type=None):
        return not self.requires_case() and 'open_case' in self.active_actions() and \
            (not case_type or self.get_module().case_type == case_type)

    def extended_build_validation(self, error_meta, xml_valid, validate_module=True):
        errors = []
        if xml_valid:
            for error in self.check_actions():
                error.update(error_meta)
                errors.append(error)

        if validate_module:
            needs_case_type = False
            needs_case_detail = False
            needs_referral_detail = False

            if self.requires_case():
                needs_case_detail = True
                needs_case_type = True
            if self.requires_case_type():
                needs_case_type = True
            if self.requires_referral():
                needs_referral_detail = True

            errors.extend(self.get_module().get_case_errors(
                needs_case_type=needs_case_type,
                needs_case_detail=needs_case_detail,
                needs_referral_detail=needs_referral_detail,
            ))

        return errors

    def get_case_updates(self, case_type):
        # This method is used by both get_all_case_properties and
        # get_usercase_properties. In the case of usercase properties, use
        # the usercase_update action, and for normal cases, use the
        # update_case action
        if case_type == self.get_module().case_type or case_type == USERCASE_TYPE:
            format_key = self.get_case_property_name_formatter()
            action = self.actions.usercase_update if case_type == USERCASE_TYPE else self.actions.update_case
            return [format_key(*item) for item in action.update.items()]
        return []

    @memoized
    def get_child_case_types(self):
        '''
        Return a list of each case type for which this Form opens a new child case.
        :return:
        '''
        child_case_types = set()
        for subcase in self.actions.subcases:
            if subcase.close_condition.type == "never":
                child_case_types.add(subcase.case_type)
        return child_case_types

    @memoized
    def get_parent_types_and_contributed_properties(self, module_case_type, case_type):
        parent_types = set()
        case_properties = set()
        for subcase in self.actions.subcases:
            if subcase.case_type == case_type:
                case_properties.update(
                    subcase.case_properties.keys()
                )
                if case_type != module_case_type and (
                        self.actions.open_case.is_active() or
                        self.actions.update_case.is_active() or
                        self.actions.close_case.is_active()):
                    parent_types.add((module_case_type, subcase.reference_id or 'parent'))
        return parent_types, case_properties

    def update_app_case_meta(self, app_case_meta):
        from corehq.apps.reports.formdetails.readable import FormQuestionResponse
        questions = {
            q['value']: FormQuestionResponse(q)
            for q in self.get_questions(self.get_app().langs, include_translations=True)
        }
        module_case_type = self.get_module().case_type
        type_meta = app_case_meta.get_type(module_case_type)
        for type_, action in self.active_actions().items():
            if type_ == 'open_case':
                type_meta.add_opener(self.unique_id, action.condition)
                self.add_property_save(
                    app_case_meta,
                    module_case_type,
                    'name',
                    questions,
                    action.name_path
                )
            if type_ == 'close_case':
                type_meta.add_closer(self.unique_id, action.condition)
            if type_ == 'update_case':
                for name, question_path in FormAction.get_action_properties(action):
                    self.add_property_save(
                        app_case_meta,
                        module_case_type,
                        name,
                        questions,
                        question_path
                    )
            if type_ == 'case_preload':
                for name, question_path in FormAction.get_action_properties(action):
                    self.add_property_load(
                        app_case_meta,
                        module_case_type,
                        name,
                        questions,
                        question_path
                    )
            if type_ == 'subcases':
                for act in action:
                    if act.is_active():
                        sub_type_meta = app_case_meta.get_type(act.case_type)
                        sub_type_meta.add_opener(self.unique_id, act.condition)
                        if act.close_condition.is_active():
                            sub_type_meta.add_closer(self.unique_id, act.close_condition)
                        for name, question_path in FormAction.get_action_properties(act):
                            self.add_property_save(
                                app_case_meta,
                                act.case_type,
                                name,
                                questions,
                                question_path
                            )


class UserRegistrationForm(FormBase):
    form_type = 'user_registration'

    username_path = StringProperty(default='username')
    password_path = StringProperty(default='password')
    data_paths = DictProperty()

    def add_stuff_to_xform(self, xform):
        super(UserRegistrationForm, self).add_stuff_to_xform(xform)
        xform.add_user_registration(self.username_path, self.password_path, self.data_paths)


class MappingItem(DocumentSchema):
    key = StringProperty()
    # lang => localized string
    value = DictProperty()

    @property
    def key_as_variable(self):
        """
        Return an xml variable name to represent this key.
        If the key has no spaces, return the key with "k" prepended.
        If the key does contain spaces, return a hash of the key with "h" prepended.
        The prepended characters prevent the variable name from starting with a
        numeral, which is illegal.
        """
        if " " not in self.key:
            return 'k{key}'.format(key=self.key)
        else:
            return 'h{hash}'.format(hash=hashlib.md5(self.key).hexdigest()[:8])


class GraphAnnotations(IndexedSchema):
    display_text = DictProperty()
    x = StringProperty()
    y = StringProperty()


class GraphSeries(DocumentSchema):
    config = DictProperty()
    data_path = StringProperty()
    x_function = StringProperty()
    y_function = StringProperty()
    radius_function = StringProperty()


class GraphConfiguration(DocumentSchema):
    config = DictProperty()
    locale_specific_config = DictProperty()
    annotations = SchemaListProperty(GraphAnnotations)
    graph_type = StringProperty()
    series = SchemaListProperty(GraphSeries)


class DetailTab(IndexedSchema):
    """
    Represents a tab in the case detail screen on the phone. Ex:
        {
            'name': 'Medical',
            'starting_index': 3
        }
    """
    header = DictProperty()
    starting_index = IntegerProperty()


class DetailColumn(IndexedSchema):
    """
    Represents a column in case selection screen on the phone. Ex:
        {
            'header': {'en': 'Sex', 'por': 'Sexo'},
            'model': 'case',
            'field': 'sex',
            'format': 'enum',
            'xpath': '.',
            'enum': [
                {'key': 'm', 'value': {'en': 'Male', 'por': 'Macho'},
                {'key': 'f', 'value': {'en': 'Female', 'por': 'Fêmea'},
            ],
        }

    """
    header = DictProperty()
    model = StringProperty()
    field = StringProperty()
    format = StringProperty()

    enum = SchemaListProperty(MappingItem)
    graph_configuration = SchemaProperty(GraphConfiguration)
    case_tile_field = StringProperty()

    late_flag = IntegerProperty(default=30)
    advanced = StringProperty(default="")
    calc_xpath = StringProperty(default=".")
    filter_xpath = StringProperty(default="")
    time_ago_interval = FloatProperty(default=365.25)

    @property
    def enum_dict(self):
        """for backwards compatibility with building 1.0 apps"""
        import warnings
        warnings.warn('You should not use enum_dict. Use enum instead',
                      DeprecationWarning)
        return dict((item.key, item.value) for item in self.enum)

    def rename_lang(self, old_lang, new_lang):
        for dct in [self.header] + [item.value for item in self.enum]:
            _rename_key(dct, old_lang, new_lang)

    @property
    def field_type(self):
        if FIELD_SEPARATOR in self.field:
            return self.field.split(FIELD_SEPARATOR, 1)[0]
        else:
            return 'property'  # equivalent to property:parent/case_property

    @property
    def field_property(self):
        if FIELD_SEPARATOR in self.field:
            return self.field.split(FIELD_SEPARATOR, 1)[1]
        else:
            return self.field

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

    @classmethod
    def wrap(cls, data):
        if data.get('format') in ('months-ago', 'years-ago'):
            data['time_ago_interval'] = cls.TimeAgoInterval.get_from_old_format(data['format'])
            data['format'] = 'time-ago'

        # Lazy migration: enum used to be a dict, now is a list
        if isinstance(data.get('enum'), dict):
            data['enum'] = sorted({'key': key, 'value': value}
                                  for key, value in data['enum'].items())

        return super(DetailColumn, cls).wrap(data)


class SortElement(IndexedSchema):
    field = StringProperty()
    type = StringProperty()
    direction = StringProperty()


class SortOnlyDetailColumn(DetailColumn):
    """This is a mock type, not intended to be part of a document"""

    @property
    def _i(self):
        """
        assert that SortOnlyDetailColumn never has ._i or .id called
        since it should never be in an app document

        """
        raise NotImplementedError()


class CaseListLookupMixin(DocumentSchema):
    """
        Allows for the addition of Android Callouts to do lookups from the CaseList
        <lookup action="" image="" name="">
            <extra key="" value = "" />
            <response key ="" />
        </lookup>
    """
    lookup_enabled = BooleanProperty(default=False)
    lookup_action = StringProperty()
    lookup_name = StringProperty()
    lookup_image = JRResourceProperty(required=False)

    lookup_extras = SchemaListProperty()
    lookup_responses = SchemaListProperty()


class Detail(IndexedSchema, CaseListLookupMixin):
    """
    Full configuration for a case selection screen

    """
    display = StringProperty(choices=['short', 'long'])

    columns = SchemaListProperty(DetailColumn)
    get_columns = IndexedSchema.Getter('columns')

    tabs = SchemaListProperty(DetailTab)
    get_tabs = IndexedSchema.Getter('tabs')

    sort_elements = SchemaListProperty(SortElement)
    filter = StringProperty()
    custom_xml = StringProperty()
    use_case_tiles = BooleanProperty()
    persist_tile_on_forms = BooleanProperty()
    pull_down_tile = BooleanProperty()

    def get_tab_spans(self):
        '''
        Return the starting and ending indices into self.columns deliminating
        the columns that should be in each tab.
        :return:
        '''
        tabs = list(self.get_tabs())
        ret = []
        for tab in tabs:
            try:
                end = tabs[tab.id + 1].starting_index
            except IndexError:
                end = len(self.columns)
            ret.append((tab.starting_index, end))
        return ret

    @parse_int([1])
    def get_column(self, i):
        return self.columns[i].with_id(i % len(self.columns), self)

    def rename_lang(self, old_lang, new_lang):
        for column in self.columns:
            column.rename_lang(old_lang, new_lang)


class CaseList(IndexedSchema, NavMenuItemMediaMixin):

    label = DictProperty()
    show = BooleanProperty(default=False)

    def rename_lang(self, old_lang, new_lang):
        _rename_key(self.label, old_lang, new_lang)


class ParentSelect(DocumentSchema):

    active = BooleanProperty(default=False)
    relationship = StringProperty(default='parent')
    module_id = StringProperty()


class DetailPair(DocumentSchema):
    short = SchemaProperty(Detail)
    long = SchemaProperty(Detail)

    @classmethod
    def wrap(cls, data):
        self = super(DetailPair, cls).wrap(data)
        self.short.display = 'short'
        self.long.display = 'long'
        return self


class CaseListForm(NavMenuItemMediaMixin):
    form_id = FormIdProperty('modules[*].case_list_form.form_id')
    label = DictProperty()

    def rename_lang(self, old_lang, new_lang):
        _rename_key(self.label, old_lang, new_lang)


class ModuleBase(IndexedSchema, NavMenuItemMediaMixin):
    name = DictProperty(unicode)
    unique_id = StringProperty()
    case_type = StringProperty()
    case_list_form = SchemaProperty(CaseListForm)
    module_filter = StringProperty()
    root_module_id = StringProperty()

    @classmethod
    def wrap(cls, data):
        if cls is ModuleBase:
            doc_type = data['doc_type']
            if doc_type == 'Module':
                return Module.wrap(data)
            elif doc_type == 'CareplanModule':
                return CareplanModule.wrap(data)
            elif doc_type == 'AdvancedModule':
                return AdvancedModule.wrap(data)
            elif doc_type == 'ReportModule':
                return ReportModule.wrap(data)
            else:
                raise ValueError('Unexpected doc_type for Module', doc_type)
        else:
            return super(ModuleBase, cls).wrap(data)

    def get_or_create_unique_id(self):
        """
        It is the caller's responsibility to save the Application
        after calling this function.

        WARNING: If called on the same doc in different requests without saving,
        this function will return a different uuid each time,
        likely causing unexpected behavior

        """
        if not self.unique_id:
            self.unique_id = FormBase.generate_id()
        return self.unique_id

    get_forms = IndexedSchema.Getter('forms')

    @parse_int([1])
    def get_form(self, i):

        try:
            return self.forms[i].with_id(i % len(self.forms), self)
        except IndexError:
            raise FormNotFoundException()

    def get_child_modules(self):
        return [
            module for module in self.get_app().get_modules()
            if module.unique_id != self.unique_id and getattr(module, 'root_module_id', None) == self.unique_id
        ]

    @property
    def root_module(self):
        if self.root_module_id:
            return self._parent.get_module_by_unique_id(self.root_module_id)

    def requires_case_details(self):
        return False

    def get_case_types(self):
        return set([self.case_type])

    def get_module_info(self):
        return {
            'id': self.id,
            'name': self.name,
        }

    def get_app(self):
        return self._parent

    def default_name(self):
        app = self.get_app()
        return trans(
            self.name,
            [app.default_language] + app.build_langs,
            include_lang=False
        )

    def rename_lang(self, old_lang, new_lang):
        _rename_key(self.name, old_lang, new_lang)
        for form in self.get_forms():
            form.rename_lang(old_lang, new_lang)
        for _, detail, _ in self.get_details():
            detail.rename_lang(old_lang, new_lang)

    def validate_detail_columns(self, columns):
        from corehq.apps.app_manager.suite_xml import FIELD_TYPE_LOCATION
        from corehq.apps.locations.util import parent_child
        hierarchy = None
        for column in columns:
            if column.format in ('enum', 'enum-image'):
                for item in column.enum:
                    key = item.key
                    # key cannot contain certain characters because it is used
                    # to generate an xpath variable name within suite.xml
                    # (names with spaces will be hashed to form the xpath
                    # variable name)
                    if not re.match('^([\w_ -]*)$', key):
                        yield {
                            'type': 'invalid id key',
                            'key': key,
                            'module': self.get_module_info(),
                        }
            elif column.field_type == FIELD_TYPE_LOCATION:
                hierarchy = hierarchy or parent_child(self.get_app().domain)
                try:
                    LocationXpath('').validate(column.field_property, hierarchy)
                except LocationXpathValidationError, e:
                    yield {
                        'type': 'invalid location xpath',
                        'details': unicode(e),
                        'module': self.get_module_info(),
                        'column': column,
                    }

    def get_form_by_unique_id(self, unique_id):
        for form in self.get_forms():
            if form.get_unique_id() == unique_id:
                return form

    def validate_for_build(self):
        errors = []
        if self.requires_case_details():
            errors.extend(self.get_case_errors(
                needs_case_type=True,
                needs_case_detail=True
            ))
        if self.case_list_form.form_id:
            try:
                form = self.get_app().get_form(self.case_list_form.form_id)
            except FormNotFoundException:
                errors.append({
                    'type': 'case list form missing',
                    'module': self.get_module_info()
                })
            else:
                if not form.is_registration_form(self.case_type):
                    errors.append({
                        'type': 'case list form not registration',
                        'module': self.get_module_info(),
                        'form': form,
                    })

        return errors

    @memoized
    def get_child_case_types(self):
        '''
        Return a list of each case type for which this module has a form that
        opens a new child case of that type.
        :return:
        '''
        child_case_types = set()
        for form in self.get_forms():
            if hasattr(form, 'get_child_case_types'):
                child_case_types.update(form.get_child_case_types())
        return child_case_types

    def get_custom_entries(self):
        """
        By default, suite entries are configured by forms, but you can also provide custom
        entries by overriding this function.

        See ReportModule for an example
        """
        return []

    def uses_media(self):
        """
        Whether the module uses media. If this returns false then media will not be generated
        for the module.
        """
        return True

class Module(ModuleBase):
    """
    A group of related forms, and configuration that applies to them all.
    Translates to a top-level menu on the phone.

    """
    module_type = 'basic'
    case_label = DictProperty()
    referral_label = DictProperty()
    forms = SchemaListProperty(Form)
    case_details = SchemaProperty(DetailPair)
    ref_details = SchemaProperty(DetailPair)
    put_in_root = BooleanProperty(default=False)
    case_list = SchemaProperty(CaseList)
    referral_list = SchemaProperty(CaseList)
    task_list = SchemaProperty(CaseList)
    parent_select = SchemaProperty(ParentSelect)

    @classmethod
    def wrap(cls, data):
        if 'details' in data:
            try:
                case_short, case_long, ref_short, ref_long = data['details']
            except ValueError:
                # "need more than 0 values to unpack"
                pass
            else:
                data['case_details'] = {
                    'short': case_short,
                    'long': case_long,
                }
                data['ref_details'] = {
                    'short': ref_short,
                    'long': ref_long,
                }
            finally:
                del data['details']
        return super(Module, cls).wrap(data)

    @classmethod
    def new_module(cls, name, lang):
        detail = Detail(
            columns=[DetailColumn(
                format='plain',
                header={(lang or 'en'): ugettext("Name")},
                field='name',
                model='case',
            )]
        )
        module = Module(
            name={(lang or 'en'): name or ugettext("Untitled Module")},
            forms=[],
            case_type='',
            case_details=DetailPair(
                short=Detail(detail.to_json()),
                long=Detail(detail.to_json()),
            ),
        )
        module.get_or_create_unique_id()
        return module

    def new_form(self, name, lang, attachment=''):
        form = Form(
            name={lang if lang else "en": name if name else _("Untitled Form")},
        )
        self.forms.append(form)
        form = self.get_form(-1)
        form.source = attachment
        return form

    def add_insert_form(self, from_module, form, index=None, with_source=False):
        if isinstance(form, Form):
            new_form = form
        elif isinstance(form, AdvancedForm) and not form.actions.get_all_actions():
            new_form = Form(
                name=form.name,
                form_filter=form.form_filter,
                media_image=form.media_image,
                media_audio=form.media_audio
            )
            new_form._parent = self
            form._parent = self
            if with_source:
                new_form.source = form.source
        else:
            raise IncompatibleFormTypeException()

        if index is not None:
            self.forms.insert(index, new_form)
        else:
            self.forms.append(new_form)
        return self.get_form(index or -1)

    def rename_lang(self, old_lang, new_lang):
        super(Module, self).rename_lang(old_lang, new_lang)
        for case_list in (self.case_list, self.referral_list):
            case_list.rename_lang(old_lang, new_lang)

    def get_details(self):
        return (
            ('case_short', self.case_details.short, True),
            ('case_long', self.case_details.long, True),
            ('ref_short', self.ref_details.short, False),
            ('ref_long', self.ref_details.long, False),
        )

    @property
    def detail_sort_elements(self):
        try:
            return self.case_details.short.sort_elements
        except Exception:
            return []

    @property
    def case_list_filter(self):
        try:
            return self.case_details.short.filter
        except AttributeError:
            return None

    def validate_for_build(self):
        errors = super(Module, self).validate_for_build()
        if not self.forms and not self.case_list.show:
            errors.append({
                'type': 'no forms or case list',
                'module': self.get_module_info(),
            })
        for sort_element in self.detail_sort_elements:
            try:
                validate_detail_screen_field(sort_element.field)
            except ValueError:
                errors.append({
                    'type': 'invalid sort field',
                    'field': sort_element.field,
                    'module': self.get_module_info(),
                })
        if self.case_list_filter:
            try:
                etree.XPath(self.case_list_filter)
            except etree.XPathSyntaxError:
                errors.append({
                    'type': 'invalid filter xpath',
                    'module': self.get_module_info(),
                    'filter': self.case_list_filter,
                })
        if self.parent_select.active and not self.parent_select.module_id:
            errors.append({
                'type': 'no parent select id',
                'module': self.get_module_info()
            })
        for detail in [self.case_details.short, self.case_details.long]:
            if detail.use_case_tiles:
                if not detail.display == "short":
                    errors.append({
                        'type': "invalid tile configuration",
                        'module': self.get_module_info(),
                        'reason': _('Case tiles may only be used for the case list (not the case details).')
                    })
                col_by_tile_field = {c.case_tile_field: c for c in detail.columns}
                for field in ["header", "top_left", "sex", "bottom_left", "date"]:
                    if field not in col_by_tile_field:
                        errors.append({
                            'type': "invalid tile configuration",
                            'module': self.get_module_info(),
                            'reason': _('A case property must be assigned to the "{}" tile field.'.format(field))
                        })
        return errors

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

    def get_case_errors(self, needs_case_type, needs_case_detail, needs_referral_detail=False):

        module_info = self.get_module_info()

        if needs_case_type and not self.case_type:
            yield {
                'type': 'no case type',
                'module': module_info,
            }

        if needs_case_detail:
            if not self.case_details.short.columns:
                yield {
                    'type': 'no case detail',
                    'module': module_info,
                }
            columns = self.case_details.short.columns + self.case_details.long.columns
            errors = self.validate_detail_columns(columns)
            for error in errors:
                yield error

        if needs_referral_detail and not self.ref_details.short.columns:
            yield {
                'type': 'no ref detail',
                'module': module_info,
            }


class AdvancedForm(IndexedFormBase, NavMenuItemMediaMixin):
    form_type = 'advanced_form'
    form_filter = StringProperty()
    actions = SchemaProperty(AdvancedFormActions)
    schedule = SchemaProperty(FormSchedule, default=None)

    @classmethod
    def wrap(cls, data):
        # lazy migration to swap keys with values in action preload dict.
        # http://manage.dimagi.com/default.asp?162213
        load_actions = data.get('actions', {}).get('load_update_cases', [])
        for action in load_actions:
            preload = action['preload']
            if preload and preload.values()[0].startswith('/'):
                action['preload'] = {v: k for k, v in preload.items()}

        return super(AdvancedForm, cls).wrap(data)

    def add_stuff_to_xform(self, xform):
        super(AdvancedForm, self).add_stuff_to_xform(xform)
        xform.add_case_and_meta_advanced(self)

    def requires_case(self):
        return bool(self.actions.load_update_cases)

    @property
    def requires(self):
        return 'case' if self.requires_case() else 'none'

    def is_registration_form(self, case_type=None):
        """
        Defined as form that opens a single case. Excludes forms that register
        sub-cases and forms that require a case.
        """
        reg_actions = self.get_registration_actions(case_type)
        return not self.requires_case() and reg_actions and \
            len(reg_actions) == 1

    def get_registration_actions(self, case_type=None):
        return [
            action for action in self.actions.get_open_actions()
            if not action.is_subcase and (not case_type or action.case_type == case_type)
        ]

    def all_other_forms_require_a_case(self):
        m = self.get_module()
        return all([form.requires == 'case' for form in m.get_forms() if form.id != self.id])

    def check_actions(self):
        errors = []

        for action in self.actions.get_subcase_actions():
            if action.parent_tag not in self.actions.get_case_tags():
                errors.append({'type': 'missing parent tag', 'case_tag': action.parent_tag})

            if isinstance(action, AdvancedOpenCaseAction):
                if not action.name_path:
                    errors.append({'type': 'case_name required', 'case_tag': action.case_tag})

                meta = self.actions.actions_meta_by_tag.get(action.parent_tag)
                if meta and meta['type'] == 'open' and meta['action'].repeat_context:
                    if not action.repeat_context or not action.repeat_context.startswith(meta['action'].repeat_context):
                        errors.append({'type': 'subcase repeat context', 'case_tag': action.case_tag})

            try:
                self.actions.get_action_hierarchy(action)
            except ValueError:
                errors.append({'type': 'circular ref', 'case_tag': action.case_tag})

            errors.extend(self.check_case_properties(
                subcase_names=action.get_property_names(),
                case_tag=action.case_tag
            ))

        for action in self.actions.get_all_actions():
            if not action.case_type and (not isinstance(action, LoadUpdateAction) or not action.auto_select):
                errors.append({'type': "no case type in action", 'case_tag': action.case_tag})

            if isinstance(action, LoadUpdateAction) and action.auto_select:
                mode = action.auto_select.mode
                if not action.auto_select.value_key:
                    key_names = {
                        AUTO_SELECT_CASE: _('Case property'),
                        AUTO_SELECT_FIXTURE: _('Lookup Table field'),
                        AUTO_SELECT_USER: _('custom user property'),
                        AUTO_SELECT_RAW: _('custom XPath expression'),
                    }
                    if mode in key_names:
                        errors.append({'type': 'auto select key', 'key_name': key_names[mode]})

                if not action.auto_select.value_source:
                    source_names = {
                        AUTO_SELECT_CASE: _('Case tag'),
                        AUTO_SELECT_FIXTURE: _('Lookup Table tag'),
                    }
                    if mode in source_names:
                        errors.append({'type': 'auto select source', 'source_name': source_names[mode]})
                elif mode == AUTO_SELECT_CASE:
                    case_tag = action.auto_select.value_source
                    if not self.actions.get_action_from_tag(case_tag):
                        errors.append({'type': 'auto select case ref', 'case_tag': action.case_tag})

            errors.extend(self.check_case_properties(
                all_names=action.get_property_names(),
                case_tag=action.case_tag
            ))

        if self.form_filter:
            if not any(action for action in self.actions.load_update_cases if not action.auto_select):
                errors.append({'type': "filtering without case"})

        def generate_paths():
            for action in self.actions.get_all_actions():
                for path in action.get_paths():
                    yield path

        errors.extend(self.check_paths(generate_paths()))

        return errors

    def extended_build_validation(self, error_meta, xml_valid, validate_module=True):
        errors = []
        if xml_valid:
            for error in self.check_actions():
                error.update(error_meta)
                errors.append(error)

        module = self.get_module()
        if module.has_schedule and not (self.schedule and self.schedule.anchor):
            error = {
                'type': 'validation error',
                'validation_message': _("All forms in this module require a visit schedule.")
            }
            error.update(error_meta)
            errors.append(error)

        if validate_module:
            errors.extend(module.get_case_errors(
                needs_case_type=False,
                needs_case_detail=module.requires_case_details(),
                needs_referral_detail=False,
            ))

        return errors

    def get_case_updates(self, case_type):
        updates = set()
        format_key = self.get_case_property_name_formatter()
        for action in self.actions.get_all_actions():
            if action.case_type == case_type:
                updates.update(format_key(*item)
                               for item in action.case_properties.iteritems())
        return updates

    @memoized
    def get_parent_types_and_contributed_properties(self, module_case_type, case_type):
        parent_types = set()
        case_properties = set()
        for subcase in self.actions.get_subcase_actions():
            if subcase.case_type == case_type:
                case_properties.update(
                    subcase.case_properties.keys()
                )
                parent = self.actions.get_action_from_tag(subcase.parent_tag)
                if parent:
                    parent_types.add((parent.case_type, subcase.parent_reference_id or 'parent'))

        return parent_types, case_properties

    def update_app_case_meta(self, app_case_meta):
        from corehq.apps.reports.formdetails.readable import FormQuestionResponse
        questions = {
            q['value']: FormQuestionResponse(q)
            for q in self.get_questions(self.get_app().langs, include_translations=True)
        }
        for action in self.actions.load_update_cases:
            for name, question_path in action.case_properties.items():
                self.add_property_save(
                    app_case_meta,
                    action.case_type,
                    name,
                    questions,
                    question_path
                )
            for question_path, name in action.preload.items():
                self.add_property_load(
                    app_case_meta,
                    action.case_type,
                    name,
                    questions,
                    question_path
                )
            if action.close_condition.is_active():
                meta = app_case_meta.get_type(action.case_type)
                meta.add_closer(self.unique_id, action.close_condition)

        for action in self.actions.open_cases:
            self.add_property_save(
                app_case_meta,
                action.case_type,
                'name',
                questions,
                action.name_path,
                action.open_condition
            )
            for name, question_path in action.case_properties.items():
                self.add_property_save(
                    app_case_meta,
                    action.case_type,
                    name,
                    questions,
                    question_path,
                    action.open_condition
                )
            meta = app_case_meta.get_type(action.case_type)
            meta.add_opener(self.unique_id, action.open_condition)
            if action.close_condition.is_active():
                meta.add_closer(self.unique_id, action.close_condition)


class AdvancedModule(ModuleBase):
    module_type = 'advanced'
    case_label = DictProperty()
    forms = SchemaListProperty(AdvancedForm)
    case_details = SchemaProperty(DetailPair)
    product_details = SchemaProperty(DetailPair)
    put_in_root = BooleanProperty(default=False)
    case_list = SchemaProperty(CaseList)
    has_schedule = BooleanProperty()

    @classmethod
    def new_module(cls, name, lang):
        detail = Detail(
            columns=[DetailColumn(
                format='plain',
                header={(lang or 'en'): ugettext("Name")},
                field='name',
                model='case',
            )]
        )

        module = AdvancedModule(
            name={(lang or 'en'): name or ugettext("Untitled Module")},
            forms=[],
            case_type='',
            case_details=DetailPair(
                short=Detail(detail.to_json()),
                long=Detail(detail.to_json()),
            ),
            product_details=DetailPair(
                short=Detail(
                    columns=[
                        DetailColumn(
                            format='plain',
                            header={(lang or 'en'): ugettext("Product")},
                            field='name',
                            model='product',
                        ),
                    ],
                ),
                long=Detail(),
            ),
        )
        module.get_or_create_unique_id()
        return module

    def new_form(self, name, lang, attachment=''):
        form = AdvancedForm(
            name={lang if lang else "en": name if name else _("Untitled Form")},
        )
        if self.has_schedule:
            form.schedule = FormSchedule()

        self.forms.append(form)
        form = self.get_form(-1)
        form.source = attachment
        return form

    def add_insert_form(self, from_module, form, index=None, with_source=False):
        if isinstance(form, AdvancedForm):
            new_form = form
        elif isinstance(form, Form):
            new_form = AdvancedForm(
                name=form.name,
                form_filter=form.form_filter,
                media_image=form.media_image,
                media_audio=form.media_audio
            )
            new_form._parent = self
            form._parent = self
            if with_source:
                new_form.source = form.source
            actions = form.active_actions()
            open = actions.get('open_case', None)
            update = actions.get('update_case', None)
            close = actions.get('close_case', None)
            preload = actions.get('case_preload', None)
            subcases = actions.get('subcases', None)
            case_type = from_module.case_type

            base_action = None
            if open:
                base_action = AdvancedOpenCaseAction(
                    case_type=case_type,
                    case_tag='open_{0}_0'.format(case_type),
                    name_path=open.name_path,
                    open_condition=open.condition,
                    case_properties=update.update if update else {},
                    )
                new_form.actions.open_cases.append(base_action)
            elif update or preload or close:
                base_action = LoadUpdateAction(
                    case_type=case_type,
                    case_tag='load_{0}_0'.format(case_type),
                    case_properties=update.update if update else {},
                    preload=preload.preload if preload else {}
                )

                if from_module.parent_select.active:
                    app = self.get_app()
                    gen = suite_xml.SuiteGenerator(app, is_usercase_in_use(app.domain))
                    select_chain = gen.get_select_chain(from_module, include_self=False)
                    for n, link in enumerate(reversed(list(enumerate(select_chain)))):
                        i, module = link
                        new_form.actions.load_update_cases.append(LoadUpdateAction(
                            case_type=module.case_type,
                            case_tag='_'.join(['parent'] * (i + 1)),
                            details_module=module.unique_id,
                            parent_tag='_'.join(['parent'] * (i + 2)) if n > 0 else ''
                        ))

                    base_action.parent_tag = 'parent'

                if close:
                    base_action.close_condition = close.condition
                new_form.actions.load_update_cases.append(base_action)

            if subcases:
                for i, subcase in enumerate(subcases):
                    open_subcase_action = AdvancedOpenCaseAction(
                        case_type=subcase.case_type,
                        case_tag='open_{0}_{1}'.format(subcase.case_type, i+1),
                        name_path=subcase.case_name,
                        open_condition=subcase.condition,
                        case_properties=subcase.case_properties,
                        repeat_context=subcase.repeat_context,
                        parent_reference_id=subcase.reference_id,
                        parent_tag=base_action.case_tag if base_action else ''
                    )
                    new_form.actions.open_cases.append(open_subcase_action)
        else:
            raise IncompatibleFormTypeException()

        if index:
            self.forms.insert(index, new_form)
        else:
            self.forms.append(new_form)
        return self.get_form(index or -1)

    def rename_lang(self, old_lang, new_lang):
        super(AdvancedModule, self).rename_lang(old_lang, new_lang)
        self.case_list.rename_lang(old_lang, new_lang)

    def requires_case_details(self):
        if self.case_list.show:
            return True

        for form in self.forms:
            if any(action.case_type == self.case_type for action in form.actions.load_update_cases):
                return True

    def all_forms_require_a_case(self):
        return all(form.requires_case() for form in self.forms)

    def get_details(self):
        return (
            ('case_short', self.case_details.short, True),
            ('case_long', self.case_details.long, True),
            ('product_short', self.product_details.short, self.get_app().commtrack_enabled),
            ('product_long', self.product_details.long, False),
        )

    def get_case_errors(self, needs_case_type, needs_case_detail, needs_referral_detail=False):

        module_info = self.get_module_info()

        if needs_case_type and not self.case_type:
            yield {
                'type': 'no case type',
                'module': module_info,
            }

        if needs_case_detail:
            if not self.case_details.short.columns:
                yield {
                    'type': 'no case detail',
                    'module': module_info,
                }
            if self.get_app().commtrack_enabled and not self.product_details.short.columns:
                for form in self.forms:
                    if self.case_list.show or \
                            any(action.show_product_stock for action in form.actions.load_update_cases):
                        yield {
                            'type': 'no product detail',
                            'module': module_info,
                        }
                        break
            columns = self.case_details.short.columns + self.case_details.long.columns
            if self.get_app().commtrack_enabled:
                columns += self.product_details.short.columns
            errors = self.validate_detail_columns(columns)
            for error in errors:
                yield error

    def validate_for_build(self):
        errors = super(AdvancedModule, self).validate_for_build()
        if not self.forms and not self.case_list.show:
            errors.append({
                'type': 'no forms or case list',
                'module': self.get_module_info(),
            })
        if self.case_list_form.form_id:
            forms = self.forms

            case_tag = None
            for form in forms:
                info = self.get_module_info()
                form_info = {"id": form.id if hasattr(form, 'id') else None, "name": form.name}

                if not form.requires_case():
                    errors.append({
                        'type': 'case list module form must require case',
                        'module': info,
                        'form': form_info,
                    })
                elif len(form.actions.load_update_cases) != 1:
                    errors.append({
                        'type': 'case list module form must require only one case',
                        'module': info,
                        'form': form_info,
                    })

                case_action = form.actions.load_update_cases[0] if form.requires_case() else None
                if case_action and case_action.case_type != self.case_type:
                    errors.append({
                        'type': 'case list module form must match module case type',
                        'module': info,
                        'form': form_info,
                    })

                # set case_tag if not already set
                case_tag = case_action.case_tag if not case_tag and case_action else case_tag
                if case_action and case_action.case_tag != case_tag:
                    errors.append({
                        'type': 'all forms in case list module must have same case management',
                        'module': info,
                        'form': form_info,
                        'expected_tag': case_tag
                    })

                if case_action and case_action.details_module and case_action.details_module != self.unique_id:
                    errors.append({
                        'type': 'forms in case list module must use modules details',
                        'module': info,
                        'form': form_info,
                    })

        return errors


class CareplanForm(IndexedFormBase, NavMenuItemMediaMixin):
    form_type = 'careplan_form'
    mode = StringProperty(required=True, choices=['create', 'update'])
    custom_case_updates = DictProperty()
    case_preload = DictProperty()

    @classmethod
    def wrap(cls, data):
        if cls is CareplanForm:
            doc_type = data['doc_type']
            if doc_type == 'CareplanGoalForm':
                return CareplanGoalForm.wrap(data)
            elif doc_type == 'CareplanTaskForm':
                return CareplanTaskForm.wrap(data)
            else:
                raise ValueError('Unexpected doc_type for CareplanForm', doc_type)
        else:
            return super(CareplanForm, cls).wrap(data)

    def add_stuff_to_xform(self, xform):
        super(CareplanForm, self).add_stuff_to_xform(xform)
        xform.add_care_plan(self)

    def get_case_updates(self, case_type):
        if case_type == self.case_type:
            format_key = self.get_case_property_name_formatter()
            return [format_key(*item) for item in self.case_updates().iteritems()]
        else:
            return []

    def get_case_type(self):
        return self.case_type

    def get_parent_case_type(self):
        return self._parent.case_type

    def get_parent_types_and_contributed_properties(self, module_case_type, case_type):
        parent_types = set()
        case_properties = set()
        if case_type == self.case_type:
            if case_type == CAREPLAN_GOAL:
                parent_types.add((module_case_type, 'parent'))
            elif case_type == CAREPLAN_TASK:
                parent_types.add((CAREPLAN_GOAL, 'goal'))
            case_properties.update(self.case_updates().keys())

        return parent_types, case_properties

    def is_registration_form(self, case_type=None):
        return self.mode == 'create' and (not case_type or self.case_type == case_type)

    def update_app_case_meta(self, app_case_meta):
        from corehq.apps.reports.formdetails.readable import FormQuestionResponse
        questions = {
            q['value']: FormQuestionResponse(q)
            for q in self.get_questions(self.get_app().langs, include_translations=True)
        }
        meta = app_case_meta.get_type(self.case_type)
        for name, question_path in self.case_updates().items():
            self.add_property_save(
                app_case_meta,
                self.case_type,
                name,
                questions,
                question_path
            )
        for name, question_path in self.case_preload.items():
            self.add_property_load(
                app_case_meta,
                self.case_type,
                name,
                questions,
                question_path
            )
        meta.add_opener(self.unique_id, FormActionCondition(
            type='always',
        ))
        meta.add_closer(self.unique_id, FormActionCondition(
            type='if',
            question=self.close_path,
            answer='yes',
        ))


class CareplanGoalForm(CareplanForm):
    case_type = CAREPLAN_GOAL
    name_path = StringProperty(required=True, default='/data/name')
    date_followup_path = StringProperty(required=True, default='/data/date_followup')
    description_path = StringProperty(required=True, default='/data/description')
    close_path = StringProperty(required=True, default='/data/close_goal')

    @classmethod
    def new_form(cls, lang, name, mode):
        action = 'Update' if mode == 'update' else 'New'
        form = CareplanGoalForm(mode=mode)
        name = name or '%s Careplan %s' % (action, CAREPLAN_CASE_NAMES[form.case_type])
        form.name = {lang: name}
        if mode == 'update':
            form.description_path = '/data/description_group/description'
        source = load_form_template('%s_%s.xml' % (form.case_type, mode))
        return form, source

    def case_updates(self):
        changes = self.custom_case_updates.copy()
        changes.update({
            'date_followup': self.date_followup_path,
            'description': self.description_path,
        })
        return changes

    def get_fixed_questions(self):
        def q(name, case_key, label):
            return {
                'name': name,
                'key': case_key,
                'label': label,
                'path': self[name]
            }
        questions = [
            q('description_path', 'description', _('Description')),
            q('date_followup_path', 'date_followup', _('Followup date')),
        ]
        if self.mode == 'create':
            return [q('name_path', 'name', _('Name'))] + questions
        else:
            return questions + [q('close_path', 'close', _('Close if'))]


class CareplanTaskForm(CareplanForm):
    case_type = CAREPLAN_TASK
    name_path = StringProperty(required=True, default='/data/task_repeat/name')
    date_followup_path = StringProperty(required=True, default='/data/date_followup')
    description_path = StringProperty(required=True, default='/data/description')
    latest_report_path = StringProperty(required=True, default='/data/progress_group/progress_update')
    close_path = StringProperty(required=True, default='/data/task_complete')

    @classmethod
    def new_form(cls, lang, name, mode):
        action = 'Update' if mode == 'update' else 'New'
        form = CareplanTaskForm(mode=mode)
        name = name or '%s Careplan %s' % (action, CAREPLAN_CASE_NAMES[form.case_type])
        form.name = {lang: name}
        if mode == 'create':
            form.date_followup_path = '/data/task_repeat/date_followup'
            form.description_path = '/data/task_repeat/description'
        source = load_form_template('%s_%s.xml' % (form.case_type, mode))
        return form, source

    def case_updates(self):
        changes = self.custom_case_updates.copy()
        changes.update({
            'date_followup': self.date_followup_path,
        })
        if self.mode == 'create':
            changes['description'] = self.description_path
        else:
            changes['latest_report'] = self.latest_report_path
        return changes

    def get_fixed_questions(self):
        def q(name, case_key, label):
            return {
                'name': name,
                'key': case_key,
                'label': label,
                'path': self[name]
            }
        questions = [
            q('date_followup_path', 'date_followup', _('Followup date')),
        ]
        if self.mode == 'create':
            return [
                q('name_path', 'name', _('Name')),
                q('description_path', 'description', _('Description')),
            ] + questions
        else:
            return questions + [
                q('latest_report_path', 'latest_report', _('Latest report')),
                q('close_path', 'close', _('Close if')),
            ]


class CareplanModule(ModuleBase):
    """
    A set of forms and configuration for managing the Care Plan workflow.
    """
    module_type = 'careplan'
    parent_select = SchemaProperty(ParentSelect)

    display_separately = BooleanProperty(default=False)
    forms = SchemaListProperty(CareplanForm)
    goal_details = SchemaProperty(DetailPair)
    task_details = SchemaProperty(DetailPair)

    @classmethod
    def new_module(cls, name, lang, target_module_id, target_case_type):
        lang = lang or 'en'
        module = CareplanModule(
            name={lang: name or ugettext("Care Plan")},
            parent_select=ParentSelect(
                active=True,
                relationship='parent',
                module_id=target_module_id
            ),
            case_type=target_case_type,
            goal_details=DetailPair(
                short=cls._get_detail(lang, 'goal_short'),
                long=cls._get_detail(lang, 'goal_long'),
            ),
            task_details=DetailPair(
                short=cls._get_detail(lang, 'task_short'),
                long=cls._get_detail(lang, 'task_long'),
            )
        )
        module.get_or_create_unique_id()
        return module

    @classmethod
    def _get_detail(cls, lang, detail_type):
        header = ugettext('Goal') if detail_type.startswith('goal') else ugettext('Task')
        columns = [
            DetailColumn(
                format='plain',
                header={lang: header},
                field='name',
                model='case'),
            DetailColumn(
                format='date',
                header={lang: ugettext("Followup")},
                field='date_followup',
                model='case')]

        if detail_type.endswith('long'):
            columns.append(DetailColumn(
                format='plain',
                header={lang: ugettext("Description")},
                field='description',
                model='case'))

        if detail_type == 'tasks_long':
            columns.append(DetailColumn(
                format='plain',
                header={lang: ugettext("Last update")},
                field='latest_report',
                model='case'))

        return Detail(type=detail_type, columns=columns)

    def add_insert_form(self, from_module, form, index=None, with_source=False):
        if isinstance(form, CareplanForm):
            if index:
                self.forms.insert(index, form)
            else:
                self.forms.append(form)
            return self.get_form(index or -1)
        else:
            raise IncompatibleFormTypeException()

    def requires_case_details(self):
        return True

    def get_case_types(self):
        return set([self.case_type]) | set(f.case_type for f in self.forms)

    def get_form_by_type(self, case_type, mode):
        for form in self.get_forms():
            if form.case_type == case_type and form.mode == mode:
                return form

    def get_details(self):
        return (
            ('%s_short' % CAREPLAN_GOAL, self.goal_details.short, True),
            ('%s_long' % CAREPLAN_GOAL, self.goal_details.long, True),
            ('%s_short' % CAREPLAN_TASK, self.task_details.short, True),
            ('%s_long' % CAREPLAN_TASK, self.task_details.long, True),
        )

    def get_case_errors(self, needs_case_type, needs_case_detail, needs_referral_detail=False):

        module_info = self.get_module_info()

        if needs_case_type and not self.case_type:
            yield {
                'type': 'no case type',
                'module': module_info,
            }

        if needs_case_detail:
            if not self.goal_details.short.columns:
                yield {
                    'type': 'no case detail for goals',
                    'module': module_info,
                }
            if not self.task_details.short.columns:
                yield {
                    'type': 'no case detail for tasks',
                    'module': module_info,
                }
            columns = self.goal_details.short.columns + self.goal_details.long.columns
            columns += self.task_details.short.columns + self.task_details.long.columns
            errors = self.validate_detail_columns(columns)
            for error in errors:
                yield error

    def validate_for_build(self):
        errors = super(CareplanModule, self).validate_for_build()
        if not self.forms:
            errors.append({
                'type': 'no forms',
                'module': self.get_module_info(),
            })
        return errors


class ReportAppConfig(DocumentSchema):
    """
    Class for configuring how a user configurable report shows up in an app
    """
    report_id = StringProperty(required=True)
    header = DictProperty()

    _report = None

    @property
    def report(self):
        from corehq.apps.userreports.models import ReportConfiguration
        if self._report is None:
            self._report = ReportConfiguration.get(self.report_id)
        return self._report

    @property
    def select_detail_id(self):
        return 'reports.{}.select'.format(self.report_id)

    @property
    def summary_detail_id(self):
        return 'reports.{}.summary'.format(self.report_id)

    @property
    def data_detail_id(self):
        return 'reports.{}.data'.format(self.report_id)

    def get_details(self):
        yield (self.select_detail_id, self.select_details(), True)
        yield (self.summary_detail_id, self.summary_details(), True)
        yield (self.data_detail_id, self.data_details(), True)

    def select_details(self):
        return Detail(custom_xml=suite_xml.Detail(
            id='reports.{}.select'.format(self.report_id),
            title=suite_xml.Text(
                locale=suite_xml.Locale(id=id_strings.report_menu()),
            ),
            fields=[
                suite_xml.Field(
                    header=suite_xml.Header(
                        text=suite_xml.Text(
                            locale=suite_xml.Locale(id=id_strings.report_name_header()),
                        )
                    ),
                    template=suite_xml.Template(
                        text=suite_xml.Text(
                            xpath=suite_xml.Xpath(function='name'))
                    ),
                )
            ]
        ).serialize())

    def summary_details(self):
        def _get_graph_fields():
            from corehq.apps.userreports.reports.specs import MultibarChartSpec
            # todo: make this less hard-coded
            for chart_config in self.report.charts:
                if isinstance(chart_config, MultibarChartSpec):
                    def _column_to_series(column):
                        return suite_xml.Series(
                            nodeset="instance('reports')/reports/report[@id='{}']/rows/row".format(self.report_id),
                            x_function="column[@id='{}']".format(chart_config.x_axis_column),
                            y_function="column[@id='{}']".format(column),
                        )
                    yield suite_xml.Field(
                        header=suite_xml.Header(text=suite_xml.Text()),
                        template=suite_xml.GraphTemplate(
                            form='graph',
                            graph=suite_xml.Graph(
                                type='bar',
                                series=[_column_to_series(c) for c in chart_config.y_axis_columns],
                            )
                        )
                    )

        return Detail(custom_xml=suite_xml.Detail(
            id='reports.{}.summary'.format(self.report_id),
            title=suite_xml.Text(
                locale=suite_xml.Locale(id=id_strings.report_menu()),
            ),
            fields=[
                suite_xml.Field(
                    header=suite_xml.Header(
                        text=suite_xml.Text(
                            locale=suite_xml.Locale(id=id_strings.report_name_header()),
                        )
                    ),
                    template=suite_xml.Template(
                        text=suite_xml.Text(
                            xpath=suite_xml.Xpath(function='name'))
                    ),
                ),
                suite_xml.Field(
                    header=suite_xml.Header(
                        text=suite_xml.Text(
                            locale=suite_xml.Locale(id=id_strings.report_description_header()),
                        )
                    ),
                    template=suite_xml.Template(
                        text=suite_xml.Text(
                            xpath=suite_xml.Xpath(function='description'))
                    ),
                ),
            ] + list(_get_graph_fields())
        ).serialize())

    def data_details(self):
        def _column_to_field(column):
            return suite_xml.Field(
                header=suite_xml.Header(
                    text=suite_xml.Text(
                        locale=suite_xml.Locale(
                            id=id_strings.report_column_header(self.report_id, column.column_id)
                        ),
                    )
                ),
                template=suite_xml.Template(
                    text=suite_xml.Text(
                        xpath=suite_xml.Xpath(function="column[@id='{}']".format(column.column_id)))
                ),
            )

        return Detail(custom_xml=suite_xml.Detail(
            id='reports.{}.data'.format(self.report_id),
            title=suite_xml.Text(
                locale=suite_xml.Locale(id=id_strings.report_name(self.report_id)),
            ),
            fields=[_column_to_field(c) for c in self.report.report_columns]
        ).serialize())

    def get_entry(self):
        return suite_xml.Entry(
            form='fixmeclayton',
            command=suite_xml.Command(
                id='reports.{}'.format(self.report_id),
                text=suite_xml.Text(
                    locale=suite_xml.Locale(id=id_strings.report_name(self.report_id)),
                ),
            ),
            datums=[
                suite_xml.SessionDatum(
                    detail_confirm=self.summary_detail_id,
                    detail_select=self.select_detail_id,
                    id='report_id_{}'.format(self.report_id),
                    nodeset="instance('reports')/reports/report[@id='{}']".format(self.report_id),
                    value='./@id',
                ),
                # you are required to select something - even if you don't use it
                suite_xml.SessionDatum(
                    detail_select=self.data_detail_id,
                    id='throwaway_{}'.format(self.report_id),
                    nodeset="instance('reports')/reports/report[@id='{}']/rows/row".format(self.report_id),
                    value="''",
                )

            ]
        )


class ReportModule(ModuleBase):
    """
    Module for user configurable reports
    """

    module_type = 'report'

    report_configs = SchemaListProperty(ReportAppConfig)
    forms = []
    _loaded = False

    @property
    @memoized
    def reports(self):
        from corehq.apps.userreports.models import ReportConfiguration
        return [
            ReportConfiguration.wrap(doc) for doc in
            get_docs(ReportConfiguration.get_db(), [r.report_id for r in self.report_configs])
        ]

    @classmethod
    def new_module(cls, name, lang):
        module = ReportModule(
            name={(lang or 'en'): name or ugettext("Reports")},
            case_type='',
        )
        module.get_or_create_unique_id()
        return module

    def _load_reports(self):
        if not self._loaded:
            # load reports in bulk to avoid hitting the database for each one
            for i, report in enumerate(self.reports):
                self.report_configs[i]._report = report
        self._loaded = True

    def get_details(self):
        self._load_reports()
        for config in self.report_configs:
            for details in config.get_details():
                yield details

    def get_custom_entries(self):
        self._load_reports()
        for config in self.report_configs:
            yield config.get_entry()

    def get_menus(self):
        yield suite_xml.Menu(
            id=id_strings.menu_id(self),
            text=suite_xml.Text(
                locale=suite_xml.Locale(id=id_strings.module_locale(self))
            ),
            commands=[
                suite_xml.Command(id=id_strings.report_command(config.report_id))
                for config in self.report_configs
            ]
        )

    def uses_media(self):
        # for now no media support for ReportModules
        return False


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
    short_odk_media_url = StringProperty()

    _meta_fields = ['_id', '_rev', 'domain', 'copy_of', 'version', 'short_url', 'short_odk_url', 'short_odk_media_url']

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
                        'short_url', 'short_odk_url', 'short_odk_media_url', 'recipients')

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


class ApplicationBase(VersionedDoc, SnapshotMixin,
                      CommCareFeatureSupportMixin):
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
    build_broken = BooleanProperty(default=False)
    # not used yet, but nice for tagging/debugging
    # currently only canonical value is 'incomplete-build',
    # for when build resources aren't found where they should be
    build_broken_reason = StringProperty()

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
    application_version = StringProperty(default=APP_V2, choices=[APP_V1, APP_V2], required=False)

    langs = StringListProperty()
    # only the languages that go in the build
    build_langs = StringListProperty()
    secure_submissions = BooleanProperty(default=False)

    # metadata for data platform
    amplifies_workers = StringProperty(
        choices=[AMPLIFIES_YES, AMPLIFIES_NO, AMPLIFIES_NOT_SET],
        default=AMPLIFIES_NOT_SET
    )
    amplifies_project = StringProperty(
        choices=[AMPLIFIES_YES, AMPLIFIES_NO, AMPLIFIES_NOT_SET],
        default=AMPLIFIES_NOT_SET
    )

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
        if 'commcare_build' in data:
            version, build_number = data['commcare_build'].split('/')
            data['build_spec'] = BuildSpec.from_string("%s/latest" % version).to_json()
            del data['commcare_build']
        if 'commcare_tag' in data:
            version, build_number = current_builds.TAG_MAP[data['commcare_tag']]
            data['build_spec'] = BuildSpec.from_string("%s/latest" % version).to_json()
            del data['commcare_tag']
        if data.has_key("built_with") and isinstance(data['built_with'], basestring):
            data['built_with'] = BuildSpec.from_string(data['built_with']).to_json()

        if 'native_input' in data:
            if 'text_input' not in data:
                data['text_input'] = 'native' if data['native_input'] else 'roman'
            del data['native_input']

        should_save = False
        if data.has_key('original_doc'):
            data['copy_history'] = [data.pop('original_doc')]
            should_save = True

        data["description"] = data.get('description') or data.get('short_description')

        self = super(ApplicationBase, cls).wrap(data)
        if not self.build_spec or self.build_spec.is_null():
            self.build_spec = get_default_build_spec(self.application_version)

        if should_save:
            self.save()

        return self

    @classmethod
    def get_latest_build(cls, domain, app_id):
        build = cls.view('app_manager/saved_app',
                                     startkey=[domain, app_id, {}],
                                     endkey=[domain, app_id],
                                     descending=True,
                                     limit=1).one()
        return build if build else None

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
                    self._latest_saved = None  # do not return this app!
        return self._latest_saved

    def set_admin_password(self, raw_password):
        salt = os.urandom(5).encode('hex')
        self.admin_password = make_password(raw_password, salt=salt)

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
            message = ('Your app requires {0} passwords '
                       'but the admin password is not {0}')

            if password_format == 'n' and self.admin_password_charset in 'ax':
                errors.append({'type': 'password_format',
                               'message': message.format('numeric')})
            if password_format == 'a' and self.admin_password_charset in 'x':
                errors.append({'type': 'password_format',
                               'message': message.format('alphanumeric')})
        return errors

    def get_build(self):
        return self.build_spec.get_build()

    @property
    def build_version(self):
        # `LooseVersion`s are smart!
        # LooseVersion('2.12.0') > '2.2'
        # (even though '2.12.0' < '2.2')
        if self.build_spec.version:
            return LooseVersion(self.build_spec.version)

    def get_preview_build(self):
        preview = self.get_build()

        for path in getattr(preview, '_attachments', {}):
            if path.startswith('Generic/WebDemo'):
                return preview
        return CommCareBuildConfig.fetch().preview.get_build()

    @property
    def commcare_minor_release(self):
        """This is mostly just for views"""
        return '%d.%d' % self.build_spec.minor_release()

    def get_build_label(self):
        for item in CommCareBuildConfig.fetch().menu:
            if item['build'].to_string() == self.build_spec.to_string():
                return item['label']
        return self.build_spec.get_label()

    @property
    def short_name(self):
        return self.name if len(self.name) <= 12 else '%s..' % self.name[:10]

    @property
    def has_careplan_module(self):
        return False

    @property
    def url_base(self):
        return get_url_base()

    @absolute_url_property
    def post_url(self):
        if self.secure_submissions:
            url_name = 'receiver_secure_post_with_app_id'
        else:
            url_name = 'receiver_post_with_app_id'
        return reverse(url_name, args=[self.domain, self.get_id])

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

    @absolute_url_property
    def hq_media_profile_url(self):
        return "%s?latest=true" % (
            reverse('download_media_profile', args=[self.domain, self._id])
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

    def validate_fixtures(self):
        if not domain_has_privilege(self.domain, privileges.LOOKUP_TABLES):
            # remote apps don't support get_forms yet.
            # for now they can circumvent the fixture limitation. sneaky bastards.
            if hasattr(self, 'get_forms'):
                for form in self.get_forms():
                    if form.has_fixtures:
                        raise PermissionDenied(_(
                            "Usage of lookup tables is not supported by your "
                            "current subscription. Please upgrade your "
                            "subscription before using this feature."
                        ))

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
                raise AppEditingError((
                    '%s Text Input is not supported '
                    'in CommCare versions before %s.%s. '
                    '(You are using %s.%s)'
                ) % ((name,) + setting_version + my_version))

    @property
    def jad_settings(self):
        settings = {
            'JavaRosa-Admin-Password': self.admin_password,
            'Profile': self.profile_loc,
            'MIDlet-Jar-URL': self.jar_url,
            #'MIDlet-Name': self.name,
            # e.g. 2011-Apr-11 20:45
            'CommCare-Release': "true",
        }
        if self.build_version < '2.8':
            settings['Build-Number'] = self.version
        return settings

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
            self.validate_fixtures()
            self.validate_jar_path()
            self.create_all_files()
        except (AppEditingError, XFormValidationError, XFormException,
                PermissionDenied) as e:
            errors.append({'type': 'error', 'message': unicode(e)})
        except Exception as e:
            if settings.DEBUG:
                raise

            # this is much less useful/actionable without a URL
            # so make sure to include the request
            logging.error('Unexpected error building app', exc_info=True,
                          extra={'request': view_utils.get_request()})
            errors.append({'type': 'error', 'message': 'unexpected error: %s' % e})
        return errors

    @absolute_url_property
    def odk_profile_url(self):
        return reverse('corehq.apps.app_manager.views.download_odk_profile', args=[self.domain, self._id])

    @absolute_url_property
    def odk_media_profile_url(self):
        return reverse('corehq.apps.app_manager.views.download_odk_media_profile', args=[self.domain, self._id])

    @property
    def odk_profile_display_url(self):
        return self.short_odk_url or self.odk_profile_url

    @property
    def odk_media_profile_display_url(self):
        return self.short_odk_media_url or self.odk_media_profile_url

    def get_odk_qr_code(self, with_media=False):
        """Returns a QR code, as a PNG to install on CC-ODK"""
        try:
            return self.lazy_fetch_attachment("qrcode.png")
        except ResourceNotFound:
            try:
                from pygooglechart import QRChart
            except ImportError:
                raise Exception(
                    "Aw shucks, someone forgot to install "
                    "the google chart library on this machine "
                    "and this feature needs it. "
                    "To get it, run easy_install pygooglechart. "
                    "Until you do that this won't work."
                )
            HEIGHT = WIDTH = 250
            code = QRChart(HEIGHT, WIDTH)
            code.add_data(self.odk_profile_url if not with_media else self.odk_media_profile_url)

            # "Level L" error correction with a 0 pixel margin
            code.set_ec('L', 0)
            f, fname = tempfile.mkstemp()
            code.download(fname)
            os.close(f)
            with open(fname, "rb") as f:
                png_data = f.read()
                self.lazy_put_attachment(png_data, "qrcode.png",
                                         content_type="image/png")
            return png_data

    def generate_shortened_url(self, url_type):
        try:
            if settings.BITLY_LOGIN:
                view_name = 'corehq.apps.app_manager.views.{}'.format(url_type)
                long_url = "{}{}".format(get_url_base(), reverse(view_name, args=[self.domain, self._id]))
                shortened_url = bitly.shorten(long_url)
            else:
                shortened_url = None
        except Exception:
            logging.exception("Problem creating bitly url for app %s. Do you have network?" % self.get_id)
        else:
            return shortened_url

    def get_short_url(self):
        if not self.short_url:
            self.short_url = self.generate_shortened_url('download_jad')
            self.save()
        return self.short_url

    def get_short_odk_url(self, with_media=False):
        if with_media:
            if not self.short_odk_media_url:
                self.short_odk_media_url = self.generate_shortened_url('download_odk_media_profile')
                self.save()
            return self.short_odk_media_url
        else:
            if not self.short_odk_url:
                self.short_odk_url = self.generate_shortened_url('download_odk_profile')
                self.save()
            return self.short_odk_url

    def fetch_jar(self):
        return self.get_jadjar().fetch_jar()

    def make_build(self, comment=None, user_id=None, previous_version=None):
        copy = super(ApplicationBase, self).make_build()
        if not copy._id:
            # I expect this always to be the case
            # but check explicitly so as not to change the _id if it exists
            copy._id = copy.get_db().server.next_uuid()

        copy.set_form_versions(previous_version)
        copy.set_media_versions(previous_version)
        copy.create_jadjar(save=True)

        try:
            # since this hard to put in a test
            # I'm putting this assert here if copy._id is ever None
            # which makes tests error
            assert copy._id
        except AssertionError:
            raise

        copy.build_comment = comment
        copy.comment_from = user_id
        if user_id:
            user = CouchUser.get(user_id)
            if not user.has_built_app:
                user.has_built_app = True
                user.save()
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

    def set_media_versions(self, previous_version):
        pass


def validate_lang(lang):
    if not re.match(r'^[a-z]{2,3}(-[a-z]*)?$', lang):
        raise ValueError("Invalid Language")


def validate_property(property):
    """
    Validate a case property name

    >>> validate_property('parent/maternal-grandmother_fullName')
    >>> validate_property('foo+bar')
    Traceback (most recent call last):
      ...
    ValueError: Invalid Property

    """
    # this regex is also copied in propertyList.ejs
    if not re.match(r'^[a-zA-Z][\w_-]*(/[a-zA-Z][\w_-]*)*$', property):
        raise ValueError("Invalid Property")


def validate_detail_screen_field(field):
    # If you change here, also change here:
    # corehq/apps/app_manager/static/app_manager/js/detail-screen-config.js
    field_re = r'^([a-zA-Z][\w_-]*:)*([a-zA-Z][\w_-]*/)*#?[a-zA-Z][\w_-]*$'
    if not re.match(field_re, field):
        raise ValueError("Invalid Sort Field")


class SavedAppBuild(ApplicationBase):

    def to_saved_build_json(self, timezone):
        data = super(SavedAppBuild, self).to_json().copy()
        for key in ('modules', 'user_registration',
                    '_attachments', 'profile', 'translations'
                    'description', 'short_description'):
            data.pop(key, None)
        built_on_user_time = ServerTime(self.built_on).user_time(timezone)
        data.update({
            'id': self.id,
            'built_on_date': built_on_user_time.ui_string(USER_DATE_FORMAT),
            'built_on_time': built_on_user_time.ui_string(USER_TIME_FORMAT),
            'build_label': self.built_with.get_label(),
            'jar_path': self.get_jar_path(),
            'short_name': self.short_name,
            'enable_offline_install': self.enable_offline_install,
        })
        comment_from = data['comment_from']
        if comment_from:
            try:
                comment_user = CouchUser.get(comment_from)
            except ResourceNotFound:
                data['comment_user_name'] = comment_from
            else:
                data['comment_user_name'] = comment_user.full_name

        return data


class Application(ApplicationBase, TranslationMixin, HQMediaMixin):
    """
    An Application that can be created entirely through the online interface

    """
    user_registration = SchemaProperty(UserRegistrationForm)
    show_user_registration = BooleanProperty(default=False, required=True)
    modules = SchemaListProperty(ModuleBase)
    name = StringProperty()
    # profile's schema is {'features': {}, 'properties': {}, 'custom_properties': {}}
    # ended up not using a schema because properties is a reserved word
    profile = DictProperty()
    use_custom_suite = BooleanProperty(default=False)
    cloudcare_enabled = BooleanProperty(default=False)
    translation_strategy = StringProperty(default='select-known',
                                          choices=app_strings.CHOICES.keys())
    commtrack_requisition_mode = StringProperty(choices=CT_REQUISITION_MODES)
    auto_gps_capture = BooleanProperty(default=False)

    @property
    @memoized
    def commtrack_enabled(self):
        if settings.UNIT_TESTING:
            return False  # override with .tests.util.commtrack_enabled
        domain_obj = Domain.get_by_name(self.domain) if self.domain else None
        return domain_obj.commtrack_enabled if domain_obj else False

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
        data.pop('commtrack_enabled', None)  # Remove me after migrating apps
        self = super(Application, cls).wrap(data)

        # make sure all form versions are None on working copies
        if not self.copy_of:
            for form in self.get_forms():
                form.version = None

        # weird edge case where multimedia_map gets set to null and causes issues
        if self.multimedia_map is None:
            self.multimedia_map = {}

        return self

    def save(self, *args, **kwargs):
        super(Application, self).save(*args, **kwargs)
        # Import loop if this is imported at the top
        # TODO: revamp so signal_connections <- models <- signals
        from corehq.apps.app_manager import signals
        signals.app_post_save.send(Application, application=self)

    def make_reversion_to_copy(self, copy):
        app = super(Application, self).make_reversion_to_copy(copy)

        for form in app.get_forms():
            # reset the form's validation cache, since the form content is
            # likely to have changed in the revert!
            form.validation_cache = None
            form.version = None

        app.build_broken = False

        return app

    @property
    def profile_url(self):
        return self.hq_profile_url

    @property
    def media_profile_url(self):
        return self.hq_media_profile_url

    @property
    def url_base(self):
        return get_url_base()

    @absolute_url_property
    def suite_url(self):
        return reverse('download_suite', args=[self.domain, self.get_id])

    @property
    def suite_loc(self):
        if self.enable_relative_suite_path:
            return './suite.xml'
        else:
            return "jr://resource/suite.xml"

    @absolute_url_property
    def media_suite_url(self):
        return reverse('download_media_suite', args=[self.domain, self.get_id])

    @property
    def media_suite_loc(self):
        if self.enable_relative_suite_path:
            return "./media_suite.xml"
        else:
            return "jr://resource/media_suite.xml"

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
                form_version = None
                try:
                    previous_form = previous_version.get_form(form.unique_id)
                    # take the previous version's compiled form as-is
                    # (generation code may have changed since last build)
                    previous_source = previous_version.fetch_attachment(filename)
                except (ResourceNotFound, FormNotFoundException):
                    pass
                else:
                    previous_hash = _hash(previous_source)

                    # hack - temporarily set my version to the previous version
                    # so that that's not treated as the diff
                    previous_form_version = previous_form.get_version()
                    form.version = previous_form_version
                    my_hash = _hash(self.fetch_xform(form=form))
                    if previous_hash == my_hash:
                        form_version = previous_form_version
                if form_version is None:
                    form.version = None
                else:
                    form.version = form_version

    def set_media_versions(self, previous_version):
        # access to .multimedia_map is slow
        prev_multimedia_map = previous_version.multimedia_map if previous_version else {}

        for path, map_item in self.multimedia_map.iteritems():
            prev_map_item = prev_multimedia_map.get(path, None)
            if prev_map_item and prev_map_item.unique_id:
                # Re-use the id so CommCare knows it's the same resource
                map_item.unique_id = prev_map_item.unique_id
            if (prev_map_item and prev_map_item.version
                    and prev_map_item.multimedia_id == map_item.multimedia_id):
                map_item.version = prev_map_item.version
            else:
                map_item.version = self.version

    def ensure_module_unique_ids(self, should_save=False):
        """
            Creates unique_ids for modules that don't have unique_id attributes
            should_save: the doc will be saved only if should_save is set to True

            WARNING: If called on the same doc in different requests without saving,
            this function will set different uuid each time,
            likely causing unexpected behavior
        """
        if any(not mod.unique_id for mod in self.modules):
            for mod in self.modules:
                mod.get_or_create_unique_id()
            if should_save:
                self.save()

    def create_app_strings(self, lang):
        gen = app_strings.CHOICES[self.translation_strategy]
        if lang == 'default':
            return gen.create_default_app_strings(self)
        else:
            return gen.create_app_strings(self, lang)

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

    def create_profile(self, is_odk=False, with_media=False, template='app_manager/profile.xml'):
        self__profile = self.profile
        app_profile = defaultdict(dict)

        for setting in commcare_settings.SETTINGS:
            setting_type = setting['type']
            setting_id = setting['id']

            if setting_type not in ('properties', 'features'):
                setting_value = None
            elif setting_id not in self__profile.get(setting_type, {}):
                if 'commcare_default' in setting and setting['commcare_default'] != setting['default']:
                    setting_value = setting['default']
                else:
                    setting_value = None
            else:
                setting_value = self__profile[setting_type][setting_id]
            if setting_value:
                app_profile[setting_type][setting_id] = {
                    'value': setting_value,
                    'force': setting.get('force', False)
                }
            # assert that it gets explicitly set once per loop
            del setting_value

        if self.case_sharing:
            app_profile['properties']['server-tether'] = {
                'force': True,
                'value': 'sync',
            }

        logo_refs = [logo_name for logo_name in self.logo_refs if logo_name in ANDROID_LOGO_PROPERTY_MAPPING]
        if logo_refs and domain_has_privilege(self.domain, privileges.COMMCARE_LOGO_UPLOADER):
            for logo_name in logo_refs:
                app_profile['properties'][ANDROID_LOGO_PROPERTY_MAPPING[logo_name]] = {
                    'value': self.logo_refs[logo_name]['path'],
                }

        if with_media:
            profile_url = self.media_profile_url if not is_odk else (self.odk_media_profile_url + '?latest=true')
        else:
            profile_url = self.profile_url if not is_odk else (self.odk_profile_url + '?latest=true')

        if toggles.CUSTOM_PROPERTIES.enabled(self.domain) and "custom_properties" in self__profile:
            app_profile['custom_properties'].update(self__profile['custom_properties'])

        return render_to_string(template, {
            'is_odk': is_odk,
            'app': self,
            'profile_url': profile_url,
            'app_profile': app_profile,
            'cc_user_domain': cc_user_domain(self.domain),
            'include_media_suite': with_media,
            'uniqueid': self.copy_of or self.id,
            'name': self.name,
            'descriptor': u"Profile File"
        }).encode('utf-8')

    @property
    def custom_suite(self):
        try:
            return self.lazy_fetch_attachment('custom_suite.xml')
        except ResourceNotFound:
            return ""

    def set_custom_suite(self, value):
        self.put_attachment(value, 'custom_suite.xml')

    def create_suite(self):
        if self.application_version == APP_V1:
            template='app_manager/suite-%s.xml' % self.application_version
            return render_to_string(template, {
                'app': self,
                'langs': ["default"] + self.build_langs
            })
        else:
            return suite_xml.SuiteGenerator(self, is_usercase_in_use(self.domain)).generate_suite()

    def create_media_suite(self):
        return suite_xml.MediaSuiteGenerator(self).generate_suite()

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
            'media_profile.xml': self.create_profile(is_odk=False, with_media=True),
            'media_profile.ccpr': self.create_profile(is_odk=True, with_media=True),
            'suite.xml': self.create_suite(),
            'media_suite.xml': self.create_media_suite(),
        }

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
        try:
            return self.modules[i].with_id(i % len(self.modules), self)
        except IndexError:
            raise ModuleNotFoundException()

    def get_user_registration(self):
        form = self.user_registration
        form._app = self
        if not (self._id and self._attachments and form.source):
            form.source = load_form_template('register_user.xhtml')
        return form

    def get_module_by_unique_id(self, unique_id):
        def matches(module):
            return module.get_or_create_unique_id() == unique_id
        for obj in self.get_modules():
            if matches(obj):
                return obj
        raise ModuleNotFoundException(
            ("Module in app '%s' with unique id '%s' not found"
             % (self.id, unique_id)))

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
        raise FormNotFoundException(
            ("Form in app '%s' with unique id '%s' not found"
             % (self.id, unique_form_id)))

    def get_form_location(self, unique_form_id):
        for m_index, module in enumerate(self.get_modules()):
            for f_index, form in enumerate(module.get_forms()):
                if unique_form_id == form.unique_id:
                    return m_index, f_index
        raise KeyError("Form in app '%s' with unique id '%s' not found" % (self.id, unique_form_id))

    @classmethod
    def new_app(cls, domain, name, application_version, lang="en"):
        app = cls(domain=domain, modules=[], name=name, langs=[lang], build_langs=[lang], application_version=application_version)
        return app

    def add_module(self, module):
        self.modules.append(module)
        return self.get_module(-1)

    def delete_module(self, module_unique_id):
        try:
            module = self.get_module_by_unique_id(module_unique_id)
        except ModuleNotFoundException:
            return None
        record = DeleteModuleRecord(
            domain=self.domain,
            app_id=self.id,
            module_id=module.id,
            module=module,
            datetime=datetime.utcnow()
        )
        del self.modules[module.id]
        record.save()
        return record

    def new_form(self, module_id, name, lang, attachment=""):
        module = self.get_module(module_id)
        return module.new_form(name, lang, attachment)

    def delete_form(self, module_unique_id, form_unique_id):
        try:
            module = self.get_module_by_unique_id(module_unique_id)
            form = self.get_form(form_unique_id)
        except (ModuleNotFoundException, FormNotFoundException):
            return None

        record = DeleteFormRecord(
            domain=self.domain,
            app_id=self.id,
            module_unique_id=module_unique_id,
            form_id=form.id,
            form=form,
            datetime=datetime.utcnow(),
        )
        record.save()
        del module['forms'][form.id]
        return record

    def rename_lang(self, old_lang, new_lang):
        validate_lang(new_lang)
        if old_lang == new_lang:
            return
        if new_lang in self.langs:
            raise AppEditingError("Language %s already exists!" % new_lang)
        for i,lang in enumerate(self.langs):
            if lang == old_lang:
                self.langs[i] = new_lang
        for module in self.get_modules():
            module.rename_lang(old_lang, new_lang)
        _rename_key(self.translations, old_lang, new_lang)

    def rearrange_modules(self, i, j):
        modules = self.modules
        try:
            modules.insert(i, modules.pop(j))
        except IndexError:
            raise RearrangeError()
        self.modules = modules

    def rearrange_forms(self, to_module_id, from_module_id, i, j):
        """
        The case type of the two modules conflict,
        ConflictingCaseTypeError is raised,
        but the rearrangement (confusingly) goes through anyway.
        This is intentional.

        """
        to_module = self.get_module(to_module_id)
        from_module = self.get_module(from_module_id)
        try:
            form = from_module.forms.pop(j)
            to_module.add_insert_form(from_module, form, index=i, with_source=True)
        except IndexError:
            raise RearrangeError()
        if to_module.case_type != from_module.case_type:
            raise ConflictingCaseTypeError()

    def scrub_source(self, source):
        def change_unique_id(form):
            unique_id = form['unique_id']
            new_unique_id = FormBase.generate_id()
            form['unique_id'] = new_unique_id
            if ("%s.xml" % unique_id) in source['_attachments']:
                source['_attachments']["%s.xml" % new_unique_id] = source['_attachments'].pop("%s.xml" % unique_id)
            return new_unique_id

        change_unique_id(source['user_registration'])
        id_changes = {}
        for m, module in enumerate(source['modules']):
            for f, form in enumerate(module['forms']):
                old_id = form['unique_id']
                new_id = change_unique_id(source['modules'][m]['forms'][f])
                id_changes[old_id] = new_id

        for reference_path in form_id_references:
            for reference in reference_path.find(source):
                if reference.value in id_changes:
                    jsonpath_update(reference, id_changes[reference.value])

    def copy_form(self, module_id, form_id, to_module_id):
        """
        The case type of the two modules conflict,
        ConflictingCaseTypeError is raised,
        but the copying (confusingly) goes through anyway.
        This is intentional.

        """
        from_module = self.get_module(module_id)
        form = from_module.get_form(form_id)
        to_module = self.get_module(to_module_id)
        self._copy_form(from_module, form, to_module, rename=True)

    def _copy_form(self, from_module, form, to_module, *args, **kwargs):
        if not form.source:
            raise BlankXFormError()
        copy_source = deepcopy(form.to_json())
        if 'unique_id' in copy_source:
            del copy_source['unique_id']

        if 'rename' in kwargs and kwargs['rename']:
            for lang, name in copy_source['name'].iteritems():
                with override(lang):
                    copy_source['name'][lang] = _('Copy of {name}').format(name=name)

        copy_form = to_module.add_insert_form(from_module, FormBase.wrap(copy_source))
        save_xform(self, copy_form, form.source)

        if from_module['case_type'] != to_module['case_type']:
            raise ConflictingCaseTypeError()

    def convert_module_to_advanced(self, module_id):
        from_module = self.get_module(module_id)

        name = {lang: u'{} (advanced)'.format(name) for lang, name in from_module.name.items()}

        case_details = deepcopy(from_module.case_details.to_json())
        to_module = AdvancedModule(
            name=name,
            forms=[],
            case_type=from_module.case_type,
            case_label=from_module.case_label,
            put_in_root=from_module.put_in_root,
            case_list=from_module.case_list,
            case_details=DetailPair.wrap(case_details),
            product_details=DetailPair(
                short=Detail(
                    columns=[
                        DetailColumn(
                            format='plain',
                            header={'en': ugettext("Product")},
                            field='name',
                            model='product',
                        ),
                    ],
                ),
                long=Detail(),
            ),
        )
        to_module.get_or_create_unique_id()
        to_module = self.add_module(to_module)

        for form in from_module.get_forms():
            self._copy_form(from_module, form, to_module)

        return to_module

    @cached_property
    def has_case_management(self):
        for module in self.get_modules():
            for form in module.get_forms():
                if len(form.active_actions()) > 0:
                    return True
        return False

    @memoized
    def case_type_exists(self, case_type):
        return case_type in self.get_case_types()

    @memoized
    def get_case_types(self):
        extra_types = set()
        if is_usercase_in_use(self.domain):
            extra_types.add(USERCASE_TYPE)
        return set(chain(*[m.get_case_types() for m in self.get_modules()])) | extra_types

    def has_media(self):
        return len(self.multimedia_map) > 0

    @memoized
    def get_xmlns_map(self):
        xmlns_map = defaultdict(list)
        for form in self.get_forms():
            xmlns_map[form.xmlns].append(form)
        return xmlns_map

    def get_form_by_xmlns(self, xmlns, log_missing=True):
        if xmlns == "http://code.javarosa.org/devicereport":
            return None
        forms = self.get_xmlns_map()[xmlns]
        if len(forms) != 1:
            if log_missing or len(forms) > 1:
                logging.error('App %s in domain %s has %s forms with xmlns %s' % (
                    self.get_id,
                    self.domain,
                    len(forms),
                    xmlns,
                ))
            return None
        else:
            form, = forms
        return form

    def get_questions(self, xmlns):
        form = self.get_form_by_xmlns(xmlns)
        if not form:
            return []
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
            errors.extend(module.validate_for_build())

        for form in self.get_forms():
            errors.extend(form.validate_for_build(validate_module=False))

            # make sure that there aren't duplicate xmlns's
            xmlns_count[form.xmlns] += 1
            for xmlns in xmlns_count:
                if xmlns_count[xmlns] > 1:
                    errors.append({'type': "duplicate xmlns", "xmlns": xmlns})

        if any(not module.unique_id for module in self.get_modules()):
            raise ModuleIdMissingException
        modules_dict = {m.unique_id: m for m in self.get_modules()}

        def _parent_select_fn(module):
            if hasattr(module, 'parent_select') and module.parent_select.active:
                return module.parent_select.module_id

        if self._has_dependency_cycle(modules_dict, _parent_select_fn):
            errors.append({'type': 'parent cycle'})

        errors.extend(self._child_module_errors(modules_dict))

        if not errors:
            errors = super(Application, self).validate_app()
        return errors

    def _has_dependency_cycle(self, modules, neighbour_id_fn):
        """
        Detect dependency cycles given modules and the neighbour_id_fn

        :param modules: A mapping of module unique_ids to Module objects
        :neighbour_id_fn: function to get the neibour module unique_id
        :return: True if there is a cycle in the module relationship graph
        """
        visited = set()
        completed = set()

        def cycle_helper(m):
            if m.id in visited:
                if m.id in completed:
                    return False
                return True
            visited.add(m.id)
            parent = modules.get(neighbour_id_fn(m), None)
            if parent is not None and cycle_helper(parent):
                return True
            completed.add(m.id)
            return False
        for module in modules.values():
            if cycle_helper(module):
                return True
        return False

    def _child_module_errors(self, modules_dict):
        module_errors = []

        def _root_module_fn(module):
            if hasattr(module, 'root_module_id'):
                return module.root_module_id

        if self._has_dependency_cycle(modules_dict, _root_module_fn):
            module_errors.append({'type': 'root cycle'})

        module_ids = set([m.unique_id for m in self.get_modules()])
        root_ids = set([_root_module_fn(m) for m in self.get_modules() if _root_module_fn(m) is not None])
        if not root_ids.issubset(module_ids):
            module_errors.append({'type': 'unknown root'})
        return module_errors

    @classmethod
    def get_by_xmlns(cls, domain, xmlns):
        r = cls.get_db().view('exports_forms/by_xmlns',
            key=[domain, {}, xmlns],
            group=True,
            stale=settings.COUCH_STALE_QUERY,
        ).one()
        return cls.get(r['value']['app']['id']) if r and 'app' in r['value'] else None

    def get_profile_setting(self, s_type, s_id):
        setting = self.profile.get(s_type, {}).get(s_id)
        if setting is not None:
            return setting
        yaml_setting = commcare_settings.SETTINGS_LOOKUP[s_type][s_id]
        for contingent in yaml_setting.get("contingent_default", []):
            if check_condition(self, contingent["condition"]):
                setting = contingent["value"]
        if setting is not None:
            return setting
        if self.build_version < yaml_setting.get("since", "0"):
            setting = yaml_setting.get("disabled_default", None)
            if setting is not None:
                return setting
        return yaml_setting.get("default")

    @property
    def has_careplan_module(self):
        return any((module for module in self.modules if isinstance(module, CareplanModule)))

    @quickcache(['self.version'])
    def get_case_metadata(self):
        from corehq.apps.reports.formdetails.readable import AppCaseMetadata
        builder = ParentCasePropertyBuilder(self)
        case_relationships = builder.get_parent_type_map(self.get_case_types())
        meta = AppCaseMetadata()

        for case_type, relationships in case_relationships.items():
            type_meta = meta.get_type(case_type)
            type_meta.relationships = relationships

        for module in self.get_modules():
            for form in module.get_forms():
                form.update_app_case_meta(meta)

        seen_types = []
        def get_children(case_type):
            seen_types.append(case_type)
            return [type_.name for type_ in meta.case_types if type_.relationships.get('parent') == case_type]

        def get_hierarchy(case_type):
            return {child: get_hierarchy(child) for child in get_children(case_type)}

        roots = [type_ for type_ in meta.case_types if not type_.relationships]
        for type_ in roots:
            meta.type_hierarchy[type_.name] = get_hierarchy(type_.name)

        for type_ in meta.case_types:
            if type_.name not in seen_types:
                meta.type_hierarchy[type_.name] = {}
                type_.error = _("Error in case type hierarchy")

        return meta


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
        return remote_app.make_remote_profile(self)

    def strip_location(self, location):
        return remote_app.strip_location(self.profile_url, location)

    def fetch_file(self, location):
        location = self.strip_location(location)
        url = urljoin(self.profile_url, location)

        try:
            content = urlopen(url).read()
        except Exception:
            raise AppEditingError('Unable to access resource url: "%s"' % url)

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

        def add_file_from_path(path, strict=False, transform=None):
            added_files = []
            # must find at least one
            try:
                tree.find(path).text
            except (TypeError, AttributeError):
                if strict:
                    raise AppEditingError("problem with file path reference!")
                else:
                    return
            for loc_node in tree.findall(path):
                loc, file = self.fetch_file(loc_node.text)
                if transform:
                    file = transform(file)
                files[loc] = file
                added_files.append(file)
            return added_files

        add_file_from_path('features/users/logo')
        try:
            suites = add_file_from_path(
                self.SUITE_XPATH,
                strict=True,
                transform=(lambda suite:
                           remote_app.make_remote_suite(self, suite))
            )
        except AppEditingError:
            raise AppEditingError(ugettext('Problem loading suite file from profile file. Is your profile file correct?'))

        for suite in suites:
            suite_xml = _parse_xml(suite)

            for tag, location in self.get_locations(suite_xml):
                location, data = self.fetch_file(location)
                if tag == 'xform' and self.build_langs:
                    try:
                        xform = XForm(data)
                    except XFormException as e:
                        raise XFormException('In file %s: %s' % (location, e))
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
            if not self.questions_map:
                return []
            self.save()
        questions = self.questions_map.get(xmlns, [])
        return questions


def get_apps_in_domain(domain, full=False, include_remote=True):
    """
    Returns all apps(not builds) in a domain

    full use applications when true, otherwise applications_brief
    """
    if full:
        view_name = 'app_manager/applications'
        startkey = [domain, None]
        endkey = [domain, None, {}]
    else:
        view_name = 'app_manager/applications_brief'
        startkey = [domain]
        endkey = [domain, {}]

    view_results = Application.get_db().view(view_name,
        startkey=startkey,
        endkey=endkey,
        include_docs=True,
    )

    remote_app_filter = None if include_remote else lambda app: not app.is_remote_app()
    wrapped_apps = [get_correct_app_class(row['doc']).wrap(row['doc']) for row in view_results]
    return filter(remote_app_filter, wrapped_apps)


def get_app(domain, app_id, wrap_cls=None, latest=False, target=None):
    """
    Utility for getting an app, making sure it's in the domain specified, and wrapping it in the right class
    (Application or RemoteApp).

    """

    if latest:
        try:
            original_app = get_db().get(app_id)
        except ResourceNotFound:
            raise Http404()
        if not domain:
            try:
                domain = original_app['domain']
            except Exception:
                raise Http404()

        if original_app.get('copy_of'):
            parent_app_id = original_app.get('copy_of')
            min_version = original_app['version'] if original_app.get('is_released') else -1
        else:
            parent_app_id = original_app['_id']
            min_version = -1

        if target == 'build':
            # get latest-build regardless of star
            couch_view = 'app_manager/saved_app'
            startkey = [domain, parent_app_id, {}]
            endkey = [domain, parent_app_id]
        else:
            # get latest starred-build
            couch_view = 'app_manager/applications'
            startkey = ['^ReleasedApplications', domain, parent_app_id, {}]
            endkey = ['^ReleasedApplications', domain, parent_app_id, min_version]

        latest_app = get_db().view(
            couch_view,
            startkey=startkey,
            endkey=endkey,
            limit=1,
            descending=True,
            include_docs=True
        ).one()

        try:
            app = latest_app['doc']
        except TypeError:
            # If no builds/starred-builds, return act as if latest=False
            app = original_app
    else:
        try:
            app = get_db().get(app_id)
        except Exception:
            raise Http404()
    if domain and app['domain'] != domain:
        raise Http404()
    try:
        cls = wrap_cls or get_correct_app_class(app)
    except DocTypeError:
        raise Http404()
    app = cls.wrap(app)
    return app

str_to_cls = {
    "Application": Application,
    "Application-Deleted": Application,
    "RemoteApp": RemoteApp,
    "RemoteApp-Deleted": RemoteApp,
}


def import_app(app_id_or_source, domain, name=None, validate_source_domain=None):
    if isinstance(app_id_or_source, basestring):
        app_id = app_id_or_source
        source = get_app(None, app_id)
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
    # Allow the wrapper to update to the current default build_spec
    if 'build_spec' in source:
        del source['build_spec']
    app = cls.from_source(source, domain)
    app.save()

    if not app.is_remote_app():
        for _, m in app.get_media_objects():
            if domain not in m.valid_domains:
                m.valid_domains.append(domain)
                m.save()

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
    module = SchemaProperty(ModuleBase)

    def undo(self):
        app = Application.get(self.app_id)
        modules = app.modules
        modules.insert(self.module_id, self.module)
        app.modules = modules
        app.save()


class DeleteFormRecord(DeleteRecord):

    app_id = StringProperty()
    module_id = IntegerProperty()
    module_unique_id = StringProperty()
    form_id = IntegerProperty()
    form = SchemaProperty(FormBase)

    def undo(self):
        app = Application.get(self.app_id)
        if self.module_unique_id is not None:
            module = app.get_module_by_unique_id(self.module_unique_id)
        else:
            module = app.modules[self.module_id]
        forms = module.forms
        forms.insert(self.form_id, self.form)
        module.forms = forms
        app.save()


class CareplanAppProperties(DocumentSchema):
    name = StringProperty()
    latest_release = StringProperty()
    case_type = StringProperty()
    goal_conf = DictProperty()
    task_conf = DictProperty()


class CareplanConfig(Document):
    domain = StringProperty()
    app_configs = SchemaDictProperty(CareplanAppProperties)

    @classmethod
    def for_domain(cls, domain):
        res = cache_core.cached_view(
            cls.get_db(),
            "domain/docs",
            key=[domain, 'CareplanConfig', None],
            reduce=False,
            include_docs=True,
            wrapper=cls.wrap)

        if len(res) > 0:
            result = res[0]
        else:
            result = None

        return result


# backwards compatibility with suite-1.0.xml
FormBase.get_command_id = lambda self: id_strings.form_command(self)
FormBase.get_locale_id = lambda self: id_strings.form_locale(self)

ModuleBase.get_locale_id = lambda self: id_strings.module_locale(self)

ModuleBase.get_case_list_command_id = lambda self: id_strings.case_list_command(self)
ModuleBase.get_case_list_locale_id = lambda self: id_strings.case_list_locale(self)

Module.get_referral_list_command_id = lambda self: id_strings.referral_list_command(self)
Module.get_referral_list_locale_id = lambda self: id_strings.referral_list_locale(self)
