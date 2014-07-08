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
from lxml import etree
from django.core.cache import cache
from django.utils.encoding import force_unicode
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext
from couchdbkit.exceptions import BadValueError, DocTypeError
from couchdbkit.ext.django.schema import *
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import Http404
from django.template.loader import render_to_string
from restkit.errors import ResourceError
from couchdbkit.resource import ResourceNotFound
from corehq import toggles, privileges
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
from corehq.apps.appstore.models import SnapshotMixin
from corehq.apps.builds.models import BuildSpec, CommCareBuildConfig, BuildRecord
from corehq.apps.hqmedia.models import HQMediaMixin
from corehq.apps.reports.templatetags.timezone_tags import utc_to_timezone
from corehq.apps.translations.models import TranslationMixin
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import cc_user_domain
from corehq.apps.domain.models import cached_property
from corehq.apps.app_manager import current_builds, app_strings, remote_app
from corehq.apps.app_manager import fixtures, suite_xml, commcare_settings
from corehq.apps.app_manager.util import split_path, save_xform, get_correct_app_class
from corehq.apps.app_manager.xform import XForm, parse_xml as _parse_xml
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from .exceptions import (
    AppEditingError,
    BlankXFormError,
    ConflictingCaseTypeError,
    RearrangeError,
    VersioningError,
    XFormError,
    XFormIdNotUnique,
    XFormValidationError,
    LocationXpathValidationError)
from corehq.apps.app_manager import id_strings

WORKFLOW_DEFAULT = 'default'
WORKFLOW_MODULE = 'module'
WORKFLOW_PREVIOUS = 'previous_screen'

AUTO_SELECT_USER = 'user'
AUTO_SELECT_FIXTURE = 'fixture'
AUTO_SELECT_CASE = 'case'
AUTO_SELECT_RAW = 'raw'

DETAIL_TYPES = ['case_short', 'case_long', 'ref_short', 'ref_long']

FIELD_SEPARATOR = ':'

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
def load_form_template(filename):
    with open(os.path.join(os.path.dirname(__file__), 'data', filename)) as f:
        return f.read()


def partial_escape(xpath):
    """
    Copied from http://stackoverflow.com/questions/275174/how-do-i-perform-html-decoding-encoding-using-python-django
    but without replacing the single quote

    """
    return mark_safe(force_unicode(xpath).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;'))


class ModuleNotFoundException(Exception):
    pass


class FormNotFoundException(Exception):
    pass


class IncompatibleFormTypeException(Exception):
    pass


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


class FormAction(DocumentSchema):
    """
    Corresponds to Case XML

    """
    condition = SchemaProperty(FormActionCondition)

    def is_active(self):
        return self.condition.type in ('if', 'always')

    @classmethod
    def get_action_paths(cls, action):
        action_properties = action.properties()
        if action.condition.type == 'if':
            yield action.condition.question
        if 'name_path' in action_properties and action.name_path:
            yield action.name_path
        if 'case_name' in action_properties:
            yield action.case_name
        if 'external_id' in action_properties and action.external_id:
            yield action.external_id
        if 'update' in action_properties:
            for _, path in action.update.items():
                yield path
        if 'case_properties' in action_properties:
            for _, path in action.case_properties.items():
                yield path
        if 'preload' in action_properties:
            for path, _ in action.preload.items():
                yield path


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


class AdvancedAction(DocumentSchema):
    case_type = StringProperty()
    case_tag = StringProperty()
    case_properties = DictProperty()
    parent_tag = StringProperty()
    parent_reference_id = StringProperty(default='parent')

    close_condition = SchemaProperty(FormActionCondition)

    def get_paths(self):
        for path in self.case_properties.values():
            yield path

        if self.close_condition.type == 'if':
            yield self.close_condition.question

    def get_property_names(self):
        return set(self.case_properties.keys())

    @property
    def case_session_var(self):
        return 'case_id_{0}'.format(self.case_tag)


class AutoSelectCase(DocumentSchema):
    """
    Configuration for auto-selecting a case.
    Attributes:
        value_source    Reference to the source of the value. For mode = fixture,
                        this represents the FixtureDataType ID. For mode = case
                        this represents the 'case_tag' for the case.
                        The mode 'user' doesn't require a value_source.
        value_key       The actual field that contains the case ID. Can be a case
                        index or a user data key or a fixture field name or the raw
                        xpath expression.

    """
    mode = StringProperty(choices=[AUTO_SELECT_USER, AUTO_SELECT_FIXTURE, AUTO_SELECT_CASE, AUTO_SELECT_RAW])
    value_source = StringProperty()
    value_key = StringProperty()


class LoadUpdateAction(AdvancedAction):
    """
    details_module:     Use the case list configuration from this module to show the cases.
    preload:            Value from the case to load into the form.
    auto_select:        Configuration for auto-selecting the case
    show_product_stock: If True list the product stock using the module's Product List configuration.
    product_program:    Only show products for this CommTrack program.
    """
    details_module = StringProperty()
    preload = DictProperty()
    auto_select = SchemaProperty(AutoSelectCase, default=None)
    show_product_stock = BooleanProperty(default=False)
    product_program = StringProperty()

    def get_paths(self):
        for path in super(LoadUpdateAction, self).get_paths():
            yield path

        for path in self.preload.values():
            yield path

    def get_property_names(self):
        names = super(LoadUpdateAction, self).get_property_names()
        names.update(self.preload.keys())
        return names


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


class AdvancedFormActions(DocumentSchema):
    load_update_cases = SchemaListProperty(LoadUpdateAction)
    open_cases = SchemaListProperty(AdvancedOpenCaseAction)

    def get_all_actions(self):
        return self.load_update_cases + self.open_cases

    def get_subcase_actions(self):
        return (a for a in self.get_all_actions() if a.parent_tag)

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

        add_actions('load', self.load_update_cases)
        add_actions('open', self.open_cases)

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
        cache.set(key, value, 7*24*60*60)  # cache for 7 days


class FormBase(DocumentSchema):
    """
    Part of a Managed Application; configuration for a form.
    Translates to a second-level menu on the phone

    """
    form_type = None

    name = DictProperty()
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
        choices=[WORKFLOW_DEFAULT, WORKFLOW_MODULE, WORKFLOW_PREVIOUS]
    )

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
                try:
                    self.validate_form()
                except XFormValidationError as e:
                    error = {'type': 'validation error', 'validation_message': unicode(e)}
                    error.update(meta)
                    errors.append(error)

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
        xform.set_version(self.get_version())

    def render_xform(self):
        xform = XForm(self.source)
        self.add_stuff_to_xform(xform)
        return xform.render()

    def get_questions(self, langs, **kwargs):
        return XForm(self.source).get_questions(langs, **kwargs)

    def get_case_property_name_formatter(self):
        """Get a function that formats case property names

        The returned function requires two arguments
        `(case_property_name, data_path)` and returns a string.
        """
        try:
            valid_paths = {question['value']: question['tag']
                           for question in self.get_questions(langs=[])}
        except XFormError as e:
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
        except XFormError:
            pass

    def rename_xform_language(self, old_code, new_code):
        source = XForm(self.source)
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
        except XFormError as e:
            errors.append({'type': 'invalid xml', 'message': unicode(e)})
        else:
            no_multimedia = not self.get_app().enable_multimedia_case_property
            for path in set(paths):
                if path not in valid_paths:
                    errors.append({'type': 'path error', 'path': path})
                elif no_multimedia and valid_paths[path] == "upload":
                    errors.append({'type': 'multimedia case property not supported', 'path': path})

        return errors


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
        if self.get_module().case_type == case_type:
            format_key = self.get_case_property_name_formatter()
            return [format_key(*item)
                    for item in self.actions.update_case.update.items()]

        return []

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
                    parent_types.add((module_case_type, 'parent'))
        return parent_types, case_properties


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

    def values(self):
        values = {
            'field': self.field,
            'type': self.type,
            'direction': self.direction,
        }

        return values


class SortOnlyDetailColumn(DetailColumn):
    """This is a mock type, not intended to be part of a document"""

    @property
    def _i(self):
        """
        assert that SortOnlyDetailColumn never has ._i or .id called
        since it should never be in an app document

        """
        raise NotImplementedError()


class Detail(IndexedSchema):
    """
    Full configuration for a case selection screen

    """
    display = StringProperty(choices=['short', 'long'])

    columns = SchemaListProperty(DetailColumn)
    get_columns = IndexedSchema.Getter('columns')

    sort_elements = SchemaListProperty(SortElement)

    @parse_int([1])
    def get_column(self, i):
        return self.columns[i].with_id(i%len(self.columns), self)

    def rename_lang(self, old_lang, new_lang):
        for column in self.columns:
            column.rename_lang(old_lang, new_lang)

    def filter_xpath(self):
        filters = []
        for i,column in enumerate(self.columns):
            if column.format == 'filter':
                value = dot_interpolate(
                    column.filter_xpath,
                    '%s_%s_%s' % (column.model, column.field, i + 1)
                )
                filters.append("(%s)" % value)
        xpath = ' and '.join(filters)
        return partial_escape(xpath)


class CaseList(IndexedSchema):

    label = DictProperty()
    show = BooleanProperty(default=False)

    def rename_lang(self, old_lang, new_lang):
        for dct in (self.label,):
            _rename_key(dct, old_lang, new_lang)


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


class ModuleBase(IndexedSchema, NavMenuItemMediaMixin):
    name = DictProperty()
    unique_id = StringProperty()
    case_type = StringProperty()

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
        self__forms = self.forms
        return self__forms[i].with_id(i%len(self.forms), self)

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
                    if not re.match('^([\w_-]*)$', key):
                        yield {
                            'type': 'invalid id key',
                            'key': key,
                            'module': self.get_module_info(),
                        }
            elif column.format == 'filter':
                try:
                    etree.XPath(column.filter_xpath or '')
                except etree.XPathSyntaxError:
                    yield {
                        'type': 'invalid filter xpath',
                        'module': self.get_module_info(),
                        'column': column,
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

    def validate_for_build(self):
        errors = []
        if not self.forms:
            errors.append({
                'type': 'no forms',
                'module': self.get_module_info(),
            })
        if self.requires_case_details():
            errors.extend(self.get_case_errors(
                needs_case_type=True,
                needs_case_detail=True
            ))
        return errors


class Module(ModuleBase):
    """
    A group of related forms, and configuration that applies to them all.
    Translates to a top-level menu on the phone.

    """
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

        if index:
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

    def validate_for_build(self):
        errors = super(Module, self).validate_for_build()
        for sort_element in self.detail_sort_elements:
            try:
                validate_detail_screen_field(sort_element.field)
            except ValueError:
                errors.append({
                    'type': 'invalid sort field',
                    'field': sort_element.field,
                    'module': self.get_module_info(),
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

    def add_stuff_to_xform(self, xform):
        super(AdvancedForm, self).add_stuff_to_xform(xform)
        xform.add_case_and_meta_advanced(self)

    @property
    def requires(self):
        return 'case' if self.actions.load_update_cases else 'none'

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

            if isinstance(action, LoadUpdateAction) and \
                    action.auto_select and action.auto_select.mode == AUTO_SELECT_CASE:
                case_tag = action.auto_select.value_source
                if not self.actions.get_action_from_tag(case_tag):
                    errors.append({'type': 'auto select ref', 'case_tag': action.case_tag})

            errors.extend(self.check_case_properties(
                subcase_names=action.get_property_names(),
                case_tag=action.case_tag
            ))

        for action in self.actions.get_all_actions():
            if not action.case_type and (not isinstance(action, LoadUpdateAction) or not action.auto_select):
                errors.append({'type': "no case type in action", 'case_tag': action.case_tag})

            errors.extend(self.check_case_properties(
                all_names=action.get_property_names(),
                case_tag=action.case_tag
            ))

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

        if validate_module:
            module = self.get_module()
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
                parent_types.add((parent.case_type, subcase.parent_reference_id or 'parent'))

        return parent_types, case_properties


class AdvancedModule(ModuleBase):
    case_label = DictProperty()
    forms = SchemaListProperty(AdvancedForm)
    case_details = SchemaProperty(DetailPair)
    product_details = SchemaProperty(DetailPair)
    put_in_root = BooleanProperty(default=False)
    case_list = SchemaProperty(CaseList)

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

            def convert_preload(preload):
                return dict(zip(preload.values(),preload.keys()))

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
                    preload=convert_preload(preload.preload) if preload else {}
                )
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
        return all(form.requires == 'case' for form in self.forms)

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
    parent_select = SchemaProperty(ParentSelect)

    display_separately = BooleanProperty(default=False)
    forms = SchemaListProperty(CareplanForm)
    goal_details = SchemaProperty(DetailPair)
    task_details = SchemaProperty(DetailPair)

    @classmethod
    def new_module(cls, app, name, lang, target_module_id, target_case_type):
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
    def by_domain(cls, domain):
        return cls.view('app_manager/applications_brief',
                        startkey=[domain],
                        endkey=[domain, {}],
                        include_docs=True,
                        #stale=settings.COUCH_STALE_QUERY,
        ).all()

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
        except (AppEditingError, XFormValidationError, XFormError,
                PermissionDenied) as e:
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
        copy.set_media_versions(previous_version)
        copy.create_jadjar(save=True)

        try:
            # since this hard to put in a test
            # I'm putting this assert here if copy._id is ever None
            # which makes tests error
            assert copy._id
            if settings.BITLY_LOGIN:
                copy.short_url = bitly.shorten(
                    get_url_base() + reverse('corehq.apps.app_manager.views.download_jad', args=[copy.domain, copy._id])
                )
                copy.short_odk_url = bitly.shorten(
                    get_url_base() + reverse('corehq.apps.app_manager.views.download_odk_profile', args=[copy.domain, copy._id])
                )
                copy.short_odk_media_url = bitly.shorten(
                    get_url_base() + reverse('corehq.apps.app_manager.views.download_odk_media_profile', args=[copy.domain, copy._id])
                )
        except AssertionError:
            raise
        except Exception:  # URLError, BitlyError
            # for offline only
            logging.exception("Problem creating bitly url for app %s. Do you have network?" % self.get_id)
            copy.short_url = None
            copy.short_odk_url = None
            copy.short_odk_media_url = None

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

    def set_media_versions(self, previous_version):
        pass


def validate_lang(lang):
    if not re.match(r'^[a-z]{2,3}(-[a-z]*)?$', lang):
        raise ValueError("Invalid Language")


def validate_property(property):
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
        data.update({
            'id': self.id,
            'built_on_date': utc_to_timezone(data['built_on'], timezone, "%b %d, %Y"),
            'built_on_time': utc_to_timezone(data['built_on'], timezone, "%H:%M %Z"),
            'build_label': self.built_with.get_label(),
            'jar_path': self.get_jar_path(),
            'short_name': self.short_name
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
    # profile's schema is {'features': {}, 'properties': {}}
    # ended up not using a schema because properties is a reserved word
    profile = DictProperty()
    use_custom_suite = BooleanProperty(default=False)
    cloudcare_enabled = BooleanProperty(default=False)
    translation_strategy = StringProperty(default='select-known',
                                          choices=app_strings.CHOICES.keys())
    commtrack_enabled = BooleanProperty(default=False)
    commtrack_requisition_mode = StringProperty(choices=CT_REQUISITION_MODES)

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

        app.broken_build = False

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
    def enable_relative_suite_path(self):
        return self.build_version >= '2.12'

    @property
    def enable_multi_sort(self):
        """
        Multi (tiered) sort is supported by apps version 2.2 or higher
        """
        return self.build_version >= '2.2'

    @property
    def enable_multimedia_case_property(self):
        """
        Multimedia case properties are supported by apps version 2.6 or higher
        """
        return self.build_version >= '2.6'

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
            pre_map_item = prev_multimedia_map.get(path, None)
            if pre_map_item and pre_map_item.version and pre_map_item.multimedia_id == map_item.multimedia_id:
                map_item.version = pre_map_item.version
            else:
                map_item.version = self.version

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
            app_profile['properties']['server-tether'] = 'sync'

        if with_media:
            profile_url = self.media_profile_url if not is_odk else (self.odk_media_profile_url + '?latest=true')
        else:
            profile_url = self.profile_url if not is_odk else (self.odk_profile_url + '?latest=true')

        return render_to_string(template, {
            'is_odk': is_odk,
            'app': self,
            'profile_url': profile_url,
            'app_profile': app_profile,
            'cc_user_domain': cc_user_domain(self.domain),
            'include_media_suite': with_media,
            'descriptor': u"Profile File"
        }).decode('utf-8')

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
            return suite_xml.SuiteGenerator(self).generate_suite()

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
        self__modules = self.modules
        try:
            return self__modules[i].with_id(i%len(self__modules), self)
        except IndexError:
            raise ModuleNotFoundException()

    def get_user_registration(self):
        form = self.user_registration
        form._app = self
        if not form.source:
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
            if source['_attachments'].has_key("%s.xml" % unique_id):
                source['_attachments']["%s.xml" % new_unique_id] = source['_attachments'].pop("%s.xml" % unique_id)

        change_unique_id(source['user_registration'])
        for m, module in enumerate(source['modules']):
            for f, form in enumerate(module['forms']):
                change_unique_id(source['modules'][m]['forms'][f])

    def copy_form(self, module_id, form_id, to_module_id):
        """
        The case type of the two modules conflict,
        ConflictingCaseTypeError is raised,
        but the copying (confusingly) goes through anyway.
        This is intentional.

        """
        from_module = self.get_module(module_id)
        form = from_module.get_form(form_id)
        if not form.source:
            raise BlankXFormError()
        copy_source = deepcopy(form.to_json())
        if 'unique_id' in copy_source:
            del copy_source['unique_id']

        to_module = self.get_module(to_module_id)
        copy_form = to_module.add_insert_form(from_module, FormBase.wrap(copy_source))
        save_xform(self, copy_form, form.source)

        if from_module['case_type'] != to_module['case_type']:
            raise ConflictingCaseTypeError()

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
        return set(chain(*[m.get_case_types() for m in self.get_modules()]))

    def has_media(self):
        return len(self.multimedia_map) > 0

    @memoized
    def get_xmlns_map(self):
        xmlns_map = defaultdict(list)
        for form in self.get_forms():
            xmlns_map[form.xmlns].append(form)
        return xmlns_map

    def get_form_by_xmlns(self, xmlns):
        if xmlns == "http://code.javarosa.org/devicereport":
            return None
        forms = self.get_xmlns_map()[xmlns]
        if len(forms) != 1:
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

        if not errors:
            errors = super(Application, self).validate_app()
        return errors

    @classmethod
    def get_by_xmlns(cls, domain, xmlns):
        r = get_db().view('exports_forms/by_xmlns', key=[domain, {}, xmlns], group=True).one()
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
        return yaml_setting.get("default")

    @property
    def has_careplan_module(self):
        return any((module for module in self.modules if isinstance(module, CareplanModule)))


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

        def add_file_from_path(path, strict=False):
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
                files[loc] = file
                added_files.append(file)
            return added_files

        add_file_from_path('features/users/logo')
        try:
            suites = add_file_from_path(self.SUITE_XPATH, strict=True)
        except AppEditingError:
            raise AppEditingError(ugettext('Problem loading suite file from profile file. Is your profile file correct?'))

        for suite in suites:
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
            if not self.questions_map:
                return []
            self.save()
        questions = self.questions_map.get(xmlns, [])
        return questions


def get_app(domain, app_id, wrap_cls=None, latest=False):
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
            raise Http404()
    if domain and app['domain'] != domain:
        raise Http404()
    try:
        cls = wrap_cls or get_correct_app_class(app)
    except DocTypeError:
        raise Http404()
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
