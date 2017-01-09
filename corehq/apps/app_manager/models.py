# coding=utf-8
"""
Application terminology

For any given application, there are a number of different documents.

The primary application document is an instance of Application.  This
document id is what you'll see in the URL on most app manager pages. Primary
application documents should have `copy_of == None` and `is_released ==
False`. When an application is saved, the field `version` is incremented.

When a user makes a build of an application, a copy of the primary
application document is made. These documents are the "versions" you see on
the deploy page. Each build document will have a different id, and the
`copy_of` field will be set to the ID of the primary application document.
Additionally, some attachments such as `profile.xml` and `suite.xml` will be
created and saved to the build doc (see `create_all_files`).

When a build is starred, this is called "releasing" the build.  The parameter
`is_released` will be set to True on the build document.

You might also run in to remote applications and applications copied to be
published on the exchange, but those are quite infrequent.
"""
import calendar
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
import datetime
import uuid
from collections import defaultdict, namedtuple
from functools import wraps
from copy import deepcopy
from mimetypes import guess_type
from urllib2 import urlopen
from urlparse import urljoin

from couchdbkit import MultipleResultsFound
import itertools
from lxml import etree
from django.core.cache import cache
from django.utils.translation import override, ugettext as _, ugettext
from couchdbkit.exceptions import BadValueError
from corehq.apps.app_manager.suite_xml.utils import get_select_chain
from corehq.apps.app_manager.suite_xml.generator import SuiteGenerator, MediaSuiteGenerator
from corehq.apps.app_manager.xpath_validator import validate_xpath
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError
from corehq.apps.users.dbaccessors.couch_users import get_display_name_for_user_id
from corehq.util.timezones.utils import get_timezone_for_domain
from dimagi.ext.couchdbkit import *
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from restkit.errors import ResourceError
from couchdbkit.resource import ResourceNotFound
from corehq import toggles, privileges
from corehq.blobs.mixin import BlobMixin
from corehq.const import USER_DATE_FORMAT, USER_TIME_FORMAT
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.app_manager.feature_support import CommCareFeatureSupportMixin
from corehq.util.quickcache import quickcache
from corehq.util.timezones.conversions import ServerTime
from dimagi.utils.couch import CriticalSection
from django_prbac.exceptions import PermissionDenied
from corehq.apps.accounting.utils import domain_has_privilege

from corehq.apps.app_manager.commcare_settings import check_condition
from corehq.apps.app_manager.const import *
from corehq.apps.app_manager.xpath import (
    dot_interpolate,
    interpolate_xpath,
    LocationXpath,
)
from corehq.apps.builds import get_default_build_spec
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.couch.undo import DeleteRecord, DELETED_SUFFIX
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.make_uuid import random_hex
from dimagi.utils.web import get_url_base, parse_int
import commcare_translations
from corehq.util import bitly
from corehq.util import view_utils
from corehq.apps.appstore.models import SnapshotMixin
from corehq.apps.builds.models import BuildSpec, BuildRecord
from corehq.apps.hqmedia.models import HQMediaMixin
from corehq.apps.translations.models import TranslationMixin
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import cc_user_domain
from corehq.apps.domain.models import cached_property, Domain
from corehq.apps.app_manager import current_builds, app_strings, remote_app, \
    id_strings, commcare_settings
from corehq.apps.app_manager.suite_xml import xml_models as suite_models
from corehq.apps.app_manager.dbaccessors import (
    get_app,
    get_latest_build_doc,
    get_latest_released_app_doc,
    domain_has_apps,
)
from corehq.apps.app_manager.util import (
    split_path,
    save_xform,
    ParentCasePropertyBuilder,
    is_usercase_in_use,
    actions_use_usercase,
    update_unique_ids,
    app_callout_templates,
    xpath_references_case,
    xpath_references_user_case,
    module_case_hierarchy_has_circular_reference,
    get_correct_app_class
)
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
    SuiteValidationError,
    VersioningError,
    XFormException,
    XFormIdNotUnique,
    XFormValidationError,
    ScheduleError,
    CaseXPathValidationError,
    UserCaseXPathValidationError,
    XFormValidationFailed)
from corehq.apps.reports.daterange import get_daterange_start_end_dates, get_simple_dateranges
from jsonpath_rw import jsonpath, parse

WORKFLOW_DEFAULT = 'default'  # go to the app main screen
WORKFLOW_ROOT = 'root'  # go to the module select screen
WORKFLOW_PARENT_MODULE = 'parent_module'  # go to the parent module's screen
WORKFLOW_MODULE = 'module'  # go to the current module's screen
WORKFLOW_PREVIOUS = 'previous_screen'  # go to the previous screen (prior to entering the form)
WORKFLOW_FORM = 'form'  # go straight to another form
ALL_WORKFLOWS = [
    WORKFLOW_DEFAULT,
    WORKFLOW_ROOT,
    WORKFLOW_PARENT_MODULE,
    WORKFLOW_MODULE,
    WORKFLOW_PREVIOUS,
    WORKFLOW_FORM,
]

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
def load_app_template(slug):
    path = os.path.join(os.path.dirname(__file__), 'static', 'app_manager', 'json', 'template_apps')
    with open(os.path.join(path, slug + '.json')) as f:
        return json.load(f)


@memoized
def load_case_reserved_words():
    with open(os.path.join(os.path.dirname(__file__), 'static', 'app_manager', 'json', 'case-reserved-words.json')) as f:
        return json.load(f)


@memoized
def load_form_template(filename):
    with open(os.path.join(os.path.dirname(__file__), 'data', filename)) as f:
        return f.read()


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
            for i, item in enumerate(items):
                yield item.with_id(i % l, instance)

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
    operator = StringProperty(choices=['=', 'selected', 'boolean_true'], default='=')

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
    # relationship = "child" for index to a parent case (default)
    # relationship = "extension" for index to a host case
    relationship = StringProperty(choices=['child', 'extension'], default='child')

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
    load_from_form = SchemaProperty(PreloadAction)  # DEPRECATED

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


class CaseIndex(DocumentSchema):
    tag = StringProperty()
    reference_id = StringProperty(default='parent')
    relationship = StringProperty(choices=['child', 'extension'], default='child')


class AdvancedAction(IndexedSchema):
    case_type = StringProperty()
    case_tag = StringProperty()
    case_properties = DictProperty()
    # case_indices = NotImplemented

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
        return bool(self.case_indices)

    @property
    def form_element_name(self):
        return "case_{}".format(self.case_tag)


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


class LoadCaseFromFixture(DocumentSchema):
    """
    fixture_nodeset:    FixtureDataType.tag
    fixture_tag:        name of the column to display in the list
    fixture_variable:   boolean if display_column actually contains the key for the localized string
    case_property:      name of the column whose value should be saved when the user selects an item
    arbitrary_datum_*:  adds an arbitrary datum with function before the action
    """
    fixture_nodeset = StringProperty()
    fixture_tag = StringProperty()
    fixture_variable = StringProperty()
    case_property = StringProperty(default='')
    auto_select = BooleanProperty(default=False)
    arbitrary_datum_id = StringProperty()
    arbitrary_datum_function = StringProperty()


class LoadUpdateAction(AdvancedAction):
    """
    details_module:           Use the case list configuration from this module to show the cases.
    preload:                  Value from the case to load into the form. Keys are question paths,
                              values are case properties.
    auto_select:              Configuration for auto-selecting the case
    load_case_from_fixture:   Configureation for loading a case using fixture data
    show_product_stock:       If True list the product stock using the module's Product List
                              configuration.
    product_program:          Only show products for this CommCare Supply program.
    """
    details_module = StringProperty()
    preload = DictProperty()
    auto_select = SchemaProperty(AutoSelectCase, default=None)
    load_case_from_fixture = SchemaProperty(LoadCaseFromFixture, default=None)
    show_product_stock = BooleanProperty(default=False)
    product_program = StringProperty()
    case_index = SchemaProperty(CaseIndex)

    @property
    def case_indices(self):
        # Allows us to ducktype AdvancedOpenCaseAction
        return [self.case_index] if self.case_index.tag else []

    @case_indices.setter
    def case_indices(self, value):
        if len(value) > 1:
            raise ValueError('A LoadUpdateAction cannot have more than one case index')
        if value:
            self.case_index = value[0]
        else:
            self.case_index = CaseIndex()

    @case_indices.deleter
    def case_indices(self):
        self.case_index = CaseIndex()

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

    @classmethod
    def wrap(cls, data):
        if 'parent_tag' in data:
            if data['parent_tag']:
                data['case_index'] = {
                    'tag': data['parent_tag'],
                    'reference_id': data.get('parent_reference_id', 'parent'),
                    'relationship': data.get('relationship', 'child')
                }
            del data['parent_tag']
            data.pop('parent_reference_id', None)
            data.pop('relationship', None)
        return super(LoadUpdateAction, cls).wrap(data)


class AdvancedOpenCaseAction(AdvancedAction):
    name_path = StringProperty()
    repeat_context = StringProperty()
    case_indices = SchemaListProperty(CaseIndex)

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

    @classmethod
    def wrap(cls, data):
        if 'parent_tag' in data:
            if data['parent_tag']:
                index = {
                    'tag': data['parent_tag'],
                    'reference_id': data.get('parent_reference_id', 'parent'),
                    'relationship': data.get('relationship', 'child')
                }
                if hasattr(data.get('case_indices'), 'append'):
                    data['case_indices'].append(index)
                else:
                    data['case_indices'] = [index]
            del data['parent_tag']
            data.pop('parent_reference_id', None)
            data.pop('relationship', None)
        return super(AdvancedOpenCaseAction, cls).wrap(data)


class AdvancedFormActions(DocumentSchema):
    load_update_cases = SchemaListProperty(LoadUpdateAction)

    open_cases = SchemaListProperty(AdvancedOpenCaseAction)

    get_load_update_actions = IndexedSchema.Getter('load_update_cases')
    get_open_actions = IndexedSchema.Getter('open_cases')

    def get_all_actions(self):
        return itertools.chain(self.get_load_update_actions(), self.get_open_actions())

    def get_subcase_actions(self):
        return (a for a in self.get_all_actions() if a.case_indices)

    def get_open_subcase_actions(self, parent_case_type=None):
        for action in self.open_cases:
            if action.case_indices:
                if not parent_case_type:
                    yield action
                else:
                    if any(self.actions_meta_by_tag[case_index.tag]['action'].case_type == parent_case_type
                           for case_index in action.case_indices):
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
                for parent in action.case_indices:
                    meta['by_parent_tag'][parent.tag] = {
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

        if not app.has_attachment(filename):
            source = ''
        else:
            source = app.lazy_fetch_attachment(filename)

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


class ScheduleVisit(IndexedSchema):
    """
    due:         Days after the anchor date that this visit is due
    starts:      Days before the due date that this visit is valid from
    expires:     Days after the due date that this visit is valid until (optional)

    repeats:     Whether this is a repeat visit (one per form allowed)
    increment:   Days after the last visit that the repeat visit occurs
    """
    due = IntegerProperty()
    starts = IntegerProperty()
    expires = IntegerProperty()
    repeats = BooleanProperty(default=False)
    increment = IntegerProperty()

    @property
    def id(self):
        """Visits are 1-based indexed"""
        _id = super(ScheduleVisit, self).id
        return _id + 1


class FormDatum(DocumentSchema):
    name = StringProperty()
    xpath = StringProperty()


class FormLink(DocumentSchema):
    """
    xpath:      xpath condition that must be true in order to open next form
    form_id:    id of next form to open
    """
    xpath = StringProperty()
    form_id = FormIdProperty('modules[*].forms[*].form_links[*].form_id')
    datums = SchemaListProperty(FormDatum)


class FormSchedule(DocumentSchema):
    """
    starts:                     Days after the anchor date that this schedule starts
    expires:                    Days after the anchor date that this schedule expires (optional)
    visits:		        List of visits in this schedule
    allow_unscheduled:          Allow unscheduled visits in this schedule
    transition_condition:       Condition under which we transition to the next phase
    termination_condition:      Condition under which we terminate the whole schedule
    """
    enabled = BooleanProperty(default=True)

    starts = IntegerProperty()
    expires = IntegerProperty()
    allow_unscheduled = BooleanProperty(default=False)
    visits = SchemaListProperty(ScheduleVisit)
    get_visits = IndexedSchema.Getter('visits')

    transition_condition = SchemaProperty(FormActionCondition)
    termination_condition = SchemaProperty(FormActionCondition)


class CustomInstance(DocumentSchema):
    """Custom instances to add to the instance block
    instance_id: 	The ID of the instance
    instance_path: 	The path where the instance can be found
    """
    instance_id = StringProperty(required=True)
    instance_path = StringProperty(required=True)


class CommentMixin(DocumentSchema):
    """
    Documentation comment for app builders and maintainers
    """
    comment = StringProperty(default='')

    @property
    def short_comment(self):
        """
        Trim comment to 500 chars (about 100 words)
        """
        return self.comment if len(self.comment) <= 500 else self.comment[:497] + '...'


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
        choices=ALL_WORKFLOWS
    )
    auto_gps_capture = BooleanProperty(default=False)
    no_vellum = BooleanProperty(default=False)
    form_links = SchemaListProperty(FormLink)
    schedule_form_id = StringProperty()
    custom_instances = SchemaListProperty(CustomInstance)

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
    def get_form(cls, form_unique_id, and_app=False):
        try:
            d = Application.get_db().view(
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

    def pre_delete_hook(self):
        raise NotImplementedError()

    def pre_move_hook(self, from_module, to_module):
        """ Called before a form is moved between modules or to a different position """
        raise NotImplementedError()

    def wrapped_xform(self):
        return XForm(self.source)

    def validate_form(self):
        vc = self.validation_cache
        if vc is None:
            # formtranslate requires all attributes to be valid xpaths, but
            # vellum namespaced attributes aren't
            form = self.wrapped_xform()
            form.strip_vellum_ns_attributes()
            try:
                if form.xml is not None:
                    validate_xform(self.get_app().domain, etree.tostring(form.xml))
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
                except XFormValidationFailed:
                    pass  # ignore this here as it gets picked up in other places

        if self.post_form_workflow == WORKFLOW_FORM:
            if not self.form_links:
                errors.append(dict(type="no form links", **meta))
            for form_link in self.form_links:
                try:
                    self.get_app().get_form(form_link.form_id)
                except FormNotFoundException:
                    errors.append(dict(type='bad form link', **meta))

        # this isn't great but two of FormBase's subclasses have form_filter
        if hasattr(self, 'form_filter') and self.form_filter:
            is_valid, message = validate_xpath(self.form_filter, allow_case_hashtags=True)
            if not is_valid:
                error = {
                    'type': 'form filter has xpath error',
                    'xpath_error': message,
                }
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
            self.unique_id = random_hex()
        return self.unique_id

    def get_app(self):
        return self._app

    def get_version(self):
        return self.version if self.version else self.get_app().version

    def add_stuff_to_xform(self, xform, build_profile_id=None):
        app = self.get_app()
        langs = app.get_build_langs(build_profile_id)
        xform.exclude_languages(langs)
        xform.set_default_language(langs[0])
        xform.normalize_itext()
        xform.strip_vellum_ns_attributes()
        xform.set_version(self.get_version())
        xform.add_missing_instances()

    def render_xform(self, build_profile_id=None):
        xform = XForm(self.source)
        self.add_stuff_to_xform(xform, build_profile_id)
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
            [app.default_language] + app.langs,
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

    def uses_usercase(self):
        raise NotImplementedError()

    def update_app_case_meta(self, app_case_meta):
        pass

    @property
    @memoized
    def case_list_modules(self):
        case_list_modules = [
            mod for mod in self.get_app().get_modules() if mod.case_list_form.form_id == self.unique_id
        ]
        return case_list_modules

    @property
    def is_case_list_form(self):
        return bool(self.case_list_modules)


class IndexedFormBase(FormBase, IndexedSchema, CommentMixin):

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
            questions = self.get_questions(langs=[], include_triggers=True, include_groups=True)
            valid_paths = {question['value']: question['tag'] for question in questions}
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
    """
        Language-specific icon and audio.
        Properties are map of lang-code to filepath
    """
    media_image = SchemaDictProperty(JRResourceProperty)
    media_audio = SchemaDictProperty(JRResourceProperty)

    @classmethod
    def wrap(cls, data):
        # ToDo - Remove after migration
        for media_attr in ('media_image', 'media_audio'):
            old_media = data.get(media_attr, None)
            if old_media and isinstance(old_media, basestring):
                new_media = {'default': old_media}
                data[media_attr] = new_media

        return super(NavMenuItemMediaMixin, cls).wrap(data)

    def _get_media_by_language(self, media_attr, lang, strict=False):
        """
        Return media-path for given language if one exists, else 1st path in the
        sorted lang->media-path list

        *args:
            media_attr: one of 'media_image' or 'media_audio'
            lang: language code
        **kwargs:
            strict: whether to return None if media-path is not set for lang or
            to return first path in sorted lang->media-path list
        """
        assert media_attr in ('media_image', 'media_audio')

        media_dict = getattr(self, media_attr)
        if not media_dict:
            return None
        if media_dict.get(lang, ''):
            return media_dict[lang]
        if not strict:
            # if the queried lang key doesn't exist,
            # return the first in the sorted list
            for lang, item in sorted(media_dict.items()):
                return item

    @property
    def default_media_image(self):
        # For older apps that were migrated
        return self.icon_by_language('default')

    @property
    def default_media_audio(self):
        # For older apps that were migrated
        return self.audio_by_language('default')

    def icon_by_language(self, lang, strict=False):
        return self._get_media_by_language('media_image', lang, strict=strict)

    def audio_by_language(self, lang, strict=False):
        return self._get_media_by_language('media_audio', lang, strict=strict)

    def _set_media(self, media_attr, lang, media_path):
        """
            Caller's responsibility to save doc.
            Currently only called from the view which saves after all Edits
        """
        assert media_attr in ('media_image', 'media_audio')

        media_dict = getattr(self, media_attr) or {}
        media_dict[lang] = media_path or ''
        setattr(self, media_attr, media_dict)

    def set_icon(self, lang, icon_path):
        self._set_media('media_image', lang, icon_path)

    def set_audio(self, lang, audio_path):
        self._set_media('media_audio', lang, audio_path)

    def _all_media_paths(self, media_attr):
        assert media_attr in ('media_image', 'media_audio')
        media_dict = getattr(self, media_attr) or {}
        valid_media_paths = {media for media in media_dict.values() if media}
        return list(valid_media_paths)

    def all_image_paths(self):
        return self._all_media_paths('media_image')

    def all_audio_paths(self):
        return self._all_media_paths('media_audio')

    def icon_app_string(self, lang, for_default=False):
        """
        Return lang/app_strings.txt translation for given lang
        if a path exists for the lang

        **kwargs:
            for_default: whether app_string is for default/app_strings.txt
        """

        if not for_default and self.icon_by_language(lang, strict=True):
            return self.icon_by_language(lang, strict=True)

        if for_default:
            return self.icon_by_language(lang, strict=False)

    def audio_app_string(self, lang, for_default=False):
        """
            see note on self.icon_app_string
        """

        if not for_default and self.audio_by_language(lang, strict=True):
            return self.audio_by_language(lang, strict=True)

        if for_default:
            return self.audio_by_language(lang, strict=False)


class Form(IndexedFormBase, NavMenuItemMediaMixin):
    form_type = 'module_form'

    form_filter = StringProperty()
    requires = StringProperty(choices=["case", "referral", "none"], default="none")
    actions = SchemaProperty(FormActions)
    case_references_data = DictProperty()

    @classmethod
    def wrap(cls, data):
        # rare schema bug: http://manage.dimagi.com/default.asp?239236
        if data.get('case_references') == []:
            del data['case_references']
        return super(Form, cls).wrap(data)

    def add_stuff_to_xform(self, xform, build_profile_id=None):
        super(Form, self).add_stuff_to_xform(xform, build_profile_id)
        xform.add_case_and_meta(self)

    def all_other_forms_require_a_case(self):
        m = self.get_module()
        return all([form.requires == 'case' for form in m.get_forms() if form.id != self.id])

    def session_var_for_action(self, action):
        module_case_type = self.get_module().case_type
        if action == 'open_case':
            return 'case_id_new_{}_0'.format(module_case_type)
        if isinstance(action, OpenSubCaseAction):
            subcase_type = action.case_type
            subcase_index = self.actions.subcases.index(action)
            opens_case = 'open_case' in self.active_actions()
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

    @memoized
    def get_action_type(self):

        if self.actions.close_case.condition.is_active():
            return 'close'
        elif (self.actions.open_case.condition.is_active() or
                self.actions.subcases):
            return 'open'
        elif self.actions.update_case.condition.is_active():
            return 'update'
        else:
            return 'none'

    @memoized
    def get_icon_help_text(self):
        messages = []

        if self.actions.open_case.condition.is_active():
            messages.append(_('This form opens a {}').format(self.get_module().case_type))

        if self.actions.subcases:
            messages.append(_('This form opens a subcase {}').format(', '.join(self.get_subcase_types())))

        if self.actions.close_case.condition.is_active():
            messages.append(_('This form closes a {}').format(self.get_module().case_type))

        elif self.requires_case():
            messages.append(_('This form updates a {}').format(self.get_module().case_type))

        return '. '.join(messages)

    def active_actions(self):
        self.get_app().assert_app_v2()
        if self.requires == 'none':
            action_types = (
                'open_case', 'update_case', 'close_case', 'subcases',
                'usercase_update', 'usercase_preload',
            )
        elif self.requires == 'case':
            action_types = (
                'update_case', 'close_case', 'case_preload', 'subcases',
                'usercase_update', 'usercase_preload', 'load_from_form',
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

    def uses_parent_case(self):
        """
        Returns True if any of the load/update properties references the
        parent case; False otherwise
        """
        return any([name.startswith('parent/')
            for name in self.actions.all_property_names()])

    def get_registration_actions(self, case_type):
        """
        :return: List of actions that create a case. Subcase actions are included
                 as long as they are not inside a repeat. If case_type is not None
                 only return actions that create a case of the specified type.
        """
        reg_actions = []
        if 'open_case' in self.active_actions() and (not case_type or self.get_module().case_type == case_type):
            reg_actions.append('open_case')

        subcase_actions = [action for action in self.actions.subcases if not action.repeat_context]
        if case_type:
            subcase_actions = [a for a in subcase_actions if a.case_type == case_type]

        reg_actions.extend(subcase_actions)
        return reg_actions

    def is_registration_form(self, case_type=None):
        reg_actions = self.get_registration_actions(case_type)
        return len(reg_actions) == 1

    def uses_usercase(self):
        return actions_use_usercase(self.active_actions())

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
    def get_subcase_types(self):
        '''
        Return a list of each case type for which this Form opens a new subcase.
        :return:
        '''
        return {subcase.case_type for subcase in self.actions.subcases
                if subcase.close_condition.type == "never" and subcase.case_type}

    @property
    def case_references(self):
        refs = self.case_references_data or {}
        if "load" not in refs and self.actions.load_from_form.preload:
            # for backward compatibility
            # preload only has one reference per question path
            preload = self.actions.load_from_form.preload
            refs["load"] = {key: [value] for key, value in preload.iteritems()}
        return refs

    @case_references.setter
    def case_references(self, refs):
        """Set case references

        format: {"load": {"/data/path": ["case_property", ...], ...}}
        """
        self.case_references_data = refs
        if self.actions.load_from_form.preload:
            self.actions.load_from_form = PreloadAction()

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
            for q in self.get_questions(self.get_app().langs, include_triggers=True,
                include_groups=True, include_translations=True)
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
            if type_ == 'update_case' or type_ == 'usercase_update':
                for name, question_path in FormAction.get_action_properties(action):
                    self.add_property_save(
                        app_case_meta,
                        USERCASE_TYPE if type_ == 'usercase_update' else module_case_type,
                        name,
                        questions,
                        question_path
                    )
            if type_ == 'case_preload' or type_ == 'load_from_form' or type_ == 'usercase_preload':
                for name, question_path in FormAction.get_action_properties(action):
                    self.add_property_load(
                        app_case_meta,
                        USERCASE_TYPE if type_ == 'usercase_preload' else module_case_type,
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
        case_loads = self.case_references.get("load", {})
        for question_path, case_properties in case_loads.iteritems():
            for name in case_properties:
                self.add_property_load(
                    app_case_meta,
                    module_case_type,
                    name,
                    questions,
                    question_path
                )


class MappingItem(DocumentSchema):
    key = StringProperty()
    # lang => localized string
    value = DictProperty()

    @property
    def treat_as_expression(self):
        """
        Returns if whether the key can be treated as a valid expression that can be included in
        condition-predicate of an if-clause for e.g. if(<expression>, value, ...)
        """
        special_chars = '{}()[]=<>."\'/'
        return any(special_char in self.key for special_char in special_chars)

    @property
    def key_as_variable(self):
        """
        Return an xml variable name to represent this key.

        If the key contains spaces or a condition-predicate of an if-clause,
        return a hash of the key with "h" prepended.
        If not, return the key with "k" prepended.

        The prepended characters prevent the variable name from starting with a
        numeral, which is illegal.
        """
        if re.search(r'\W', self.key) or self.treat_as_expression:
            return 'h{hash}'.format(hash=hashlib.md5(self.key).hexdigest()[:8])
        else:
            return 'k{key}'.format(key=self.key)

    def key_as_condition(self, property):
        if self.treat_as_expression:
            condition = dot_interpolate(self.key, property)
            return u"{condition}".format(condition=condition)
        else:
            return u"{property} = '{key}'".format(
                property=property,
                key=self.key
            )

    def ref_to_key_variable(self, index, sort_or_display):
        if sort_or_display == "sort":
            key_as_var = "{}, ".format(index)
        elif sort_or_display == "display":
            key_as_var = "${var_name}, ".format(var_name=self.key_as_variable)

        return key_as_var


class GraphAnnotations(IndexedSchema):
    display_text = DictProperty()
    x = StringProperty()
    y = StringProperty()


class GraphSeries(DocumentSchema):
    config = DictProperty()
    locale_specific_config = DictProperty()
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
    Represents a tab in the case detail screen on the phone.
    Each tab is itself a detail, nested inside the app's "main" detail.
    """
    header = DictProperty()

    # The first index, of all fields in the parent detail, that belongs to this tab
    starting_index = IntegerProperty()

    # A tab may be associated with a nodeset, resulting in a detail that
    # iterates through sub-nodes of an entity rather than a single entity
    has_nodeset = BooleanProperty(default=False)
    nodeset = StringProperty()


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

    @classmethod
    def from_json(cls, data):
        from corehq.apps.app_manager.views.media_utils import interpolate_media_path

        to_ret = cls.wrap(data)
        if to_ret.format == 'enum-image':
            # interpolate icons-paths
            for item in to_ret.enum:
                for lang, path in item.value.iteritems():
                    item.value[lang] = interpolate_media_path(path)
        return to_ret


class SortElement(IndexedSchema):
    field = StringProperty()
    type = StringProperty()
    direction = StringProperty()
    display = DictProperty()

    def has_display_values(self):
        return any(s.strip() != '' for s in self.display.values())

class CaseListLookupMixin(DocumentSchema):
    """
    Allows for the addition of Android Callouts to do lookups from the CaseList

        <lookup action="" image="" name="">
            <extra key="" value="" />
            <response key="" />
            <field>
                <header><text><locale id=""/></text></header>
                <template><text><xpath function=""/></text></template>
            </field>
        </lookup>

    """
    lookup_enabled = BooleanProperty(default=False)
    lookup_autolaunch = BooleanProperty(default=False)
    lookup_action = StringProperty()
    lookup_name = StringProperty()
    lookup_image = JRResourceProperty(required=False)

    lookup_extras = SchemaListProperty()
    lookup_responses = SchemaListProperty()

    lookup_display_results = BooleanProperty(default=False)  # Display callout results in case list?
    lookup_field_header = DictProperty()
    lookup_field_template = StringProperty()


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

    # If True, a small tile will display the case name after selection.
    persist_case_context = BooleanProperty()
    persistent_case_context_xml = StringProperty(default='case_name')

    # Custom variables to add into the <variables /> node
    custom_variables = StringProperty()

    # If True, use case tiles in the case list
    use_case_tiles = BooleanProperty()
    # If given, use this string for the case tile markup instead of the default temaplte
    custom_xml = StringProperty()

    persist_tile_on_forms = BooleanProperty()
    # If True, the in form tile can be pulled down to reveal all the case details.
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


class CaseSearchProperty(DocumentSchema):
    """
    Case properties available to search on.
    """
    name = StringProperty()
    label = DictProperty()


class DefaultCaseSearchProperty(DocumentSchema):
    """Case Properties with fixed value to search on"""
    property = StringProperty()
    default_value = StringProperty()


class CaseSearch(DocumentSchema):
    """
    Properties and search command label
    """
    command_label = DictProperty(default={'en': 'Search All Cases'})
    properties = SchemaListProperty(CaseSearchProperty)
    relevant = StringProperty(default=CLAIM_DEFAULT_RELEVANT_CONDITION)
    include_closed = BooleanProperty(default=False)
    default_properties = SchemaListProperty(DefaultCaseSearchProperty)


class ParentSelect(DocumentSchema):

    active = BooleanProperty(default=False)
    relationship = StringProperty(default='parent')
    module_id = StringProperty()


class FixtureSelect(DocumentSchema):
    """
    Configuration for creating a details screen from a fixture which can be used to pre-filter
    cases prior to displaying the case list.

    fixture_type:       FixtureDataType.tag
    display_column:     name of the column to display in the list
    localize:           boolean if display_column actually contains the key for the localized string
    variable_column:    name of the column whose value should be saved when the user selects an item
    xpath:              xpath expression to use as the case filter
    """
    active = BooleanProperty(default=False)
    fixture_type = StringProperty()
    display_column = StringProperty()
    localize = BooleanProperty(default=False)
    variable_column = StringProperty()
    xpath = StringProperty(default='')


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


class ModuleBase(IndexedSchema, NavMenuItemMediaMixin, CommentMixin):
    name = DictProperty(unicode)
    unique_id = StringProperty()
    case_type = StringProperty()
    case_list_form = SchemaProperty(CaseListForm)
    module_filter = StringProperty()
    root_module_id = StringProperty()
    fixture_select = SchemaProperty(FixtureSelect)
    auto_select_case = BooleanProperty(default=False)

    @property
    def is_surveys(self):
        return self.case_type == ""

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
            elif doc_type == 'ShadowModule':
                return ShadowModule.wrap(data)
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
            self.unique_id = random_hex()
        return self.unique_id

    get_forms = IndexedSchema.Getter('forms')

    get_suite_forms = IndexedSchema.Getter('forms')

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
            return self._parent.get_module_by_unique_id(self.root_module_id,
                   error=_("Could not find parent menu for '{}'").format(self.default_name()))

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
            [app.default_language] + app.langs,
            include_lang=False
        )

    def rename_lang(self, old_lang, new_lang):
        _rename_key(self.name, old_lang, new_lang)
        for form in self.get_forms():
            form.rename_lang(old_lang, new_lang)
        for _, detail, _ in self.get_details():
            detail.rename_lang(old_lang, new_lang)

    def validate_detail_columns(self, columns):
        from corehq.apps.app_manager.suite_xml.const import FIELD_TYPE_LOCATION
        from corehq.apps.locations.util import parent_child
        hierarchy = None
        for column in columns:
            if column.field_type == FIELD_TYPE_LOCATION:
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
        needs_case_detail = self.requires_case_details()
        needs_case_type = needs_case_detail or len([1 for f in self.get_forms() if f.is_registration_form()])
        if needs_case_detail or needs_case_type:
            errors.extend(self.get_case_errors(
                needs_case_type=needs_case_type,
                needs_case_detail=needs_case_detail
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
        if self.module_filter:
            is_valid, message = validate_xpath(self.module_filter)
            if not is_valid:
                errors.append({
                    'type': 'module filter has xpath error',
                    'xpath_error': message,
                    'module': self.get_module_info(),
                })

        return errors

    @memoized
    def get_subcase_types(self):
        '''
        Return a set of each case type for which this module has a form that
        opens a new subcase of that type.
        '''
        subcase_types = set()
        for form in self.get_forms():
            if hasattr(form, 'get_subcase_types'):
                subcase_types.update(form.get_subcase_types())
        return subcase_types

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

    def uses_usercase(self):
        return False

    def add_insert_form(self, from_module, form, index=None, with_source=False):
        raise IncompatibleFormTypeException()


class ModuleDetailsMixin():

    @classmethod
    def wrap_details(cls, data):
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
        return data

    @property
    def case_list_filter(self):
        try:
            return self.case_details.short.filter
        except AttributeError:
            return None

    @property
    def detail_sort_elements(self):
        try:
            return self.case_details.short.sort_elements
        except Exception:
            return []

    def rename_lang(self, old_lang, new_lang):
        super(Module, self).rename_lang(old_lang, new_lang)
        for case_list in (self.case_list, self.referral_list):
            case_list.rename_lang(old_lang, new_lang)

    def export_json(self, dump_json=True, keep_unique_id=False):
        source = self.to_json()
        if not keep_unique_id:
            for form in source['forms']:
                del form['unique_id']
        return json.dumps(source) if dump_json else source

    def get_details(self):
        return (
            ('case_short', self.case_details.short, True),
            ('case_long', self.case_details.long, True),
            ('ref_short', self.ref_details.short, False),
            ('ref_long', self.ref_details.long, False),
        )

    def validate_details_for_build(self):
        errors = []
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
                case_list_filter = interpolate_xpath(self.case_list_filter)
                etree.XPath(case_list_filter)
            except (etree.XPathSyntaxError, CaseXPathValidationError):
                errors.append({
                    'type': 'invalid filter xpath',
                    'module': self.get_module_info(),
                    'filter': self.case_list_filter,
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


class Module(ModuleBase, ModuleDetailsMixin):
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
    search_config = SchemaProperty(CaseSearch)
    display_style = StringProperty(default='list')

    @classmethod
    def wrap(cls, data):
        data = cls.wrap_details(data)
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
            case_label={(lang or 'en'): 'Cases'},
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

    def validate_for_build(self):
        errors = super(Module, self).validate_for_build() + self.validate_details_for_build()
        if not self.forms and not self.case_list.show:
            errors.append({
                'type': 'no forms or case list',
                'module': self.get_module_info(),
            })

        if module_case_hierarchy_has_circular_reference(self):
            errors.append({
                'type': 'circular case hierarchy',
                'module': self.get_module_info(),
            })

        return errors

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

    def uses_usercase(self):
        """Return True if this module has any forms that use the usercase.
        """
        return any(form.uses_usercase() for form in self.get_forms())

    def grid_display_style(self):
        return self.display_style == 'grid'

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

    def pre_delete_hook(self):
        try:
            self.disable_schedule()
        except (ScheduleError, TypeError, AttributeError) as e:
            logging.error("There was a {error} while running the pre_delete_hook on {form_id}. "
                          "There is probably nothing to worry about, but you could check to make sure "
                          "that there are no issues with this form.".format(error=e, form_id=self.unique_id))
            pass

    def pre_move_hook(self, from_module, to_module):
        if from_module != to_module:
            try:
                self.disable_schedule()
            except (ScheduleError, TypeError, AttributeError) as e:
                logging.error("There was a {error} while running the pre_move_hook on {form_id}. "
                              "There is probably nothing to worry about, but you could check to make sure "
                              "that there are no issues with this module.".format(error=e, form_id=self.unique_id))
                pass

    def add_stuff_to_xform(self, xform, build_profile_id=None):
        super(AdvancedForm, self).add_stuff_to_xform(xform, build_profile_id)
        xform.add_case_and_meta_advanced(self)

    def requires_case(self):
        """Form requires a case that must be selected by the user (excludes autoloaded cases)
        """
        return any(not action.auto_select for action in self.actions.load_update_cases)

    @property
    def requires(self):
        return 'case' if self.requires_case() else 'none'

    def is_registration_form(self, case_type=None):
        """
        Defined as form that opens a single case. If the case is a sub-case then
        the form is only allowed to load parent cases (and any auto-selected cases).
        """
        reg_actions = self.get_registration_actions(case_type)
        if len(reg_actions) != 1:
            return False

        load_actions = [action for action in self.actions.load_update_cases if not action.auto_select]
        if not load_actions:
            return True

        reg_action = reg_actions[0]
        if not reg_action.case_indices:
            return False

        actions_by_tag = deepcopy(self.actions.actions_meta_by_tag)
        actions_by_tag.pop(reg_action.case_tag)

        def check_parents(tag):
            """Recursively check parent actions to ensure that all actions for this form are
            either parents of the registration action or else auto-select actions.
            """
            if not tag:
                return not actions_by_tag or all(
                    getattr(a['action'], 'auto_select', False) for a in actions_by_tag.values()
                )

            try:
                parent = actions_by_tag.pop(tag)
            except KeyError:
                return False

            return all(check_parents(p.tag) for p in parent['action'].case_indices)

        return all(check_parents(parent.tag) for parent in reg_action.case_indices)

    def get_registration_actions(self, case_type=None):
        """
        :return: List of actions that create a case. Subcase actions are included
                 as long as they are not inside a repeat. If case_type is not None
                 only return actions that create a case of the specified type.
        """
        registration_actions = [
            action for action in self.actions.get_open_actions()
            if not action.is_subcase or not action.repeat_context
        ]
        if case_type:
            registration_actions = [a for a in registration_actions if a.case_type == case_type]

        return registration_actions

    def uses_case_type(self, case_type, invert_match=False):
        def match(ct):
            matches = ct == case_type
            return not matches if invert_match else matches

        return any(action for action in self.actions.load_update_cases if match(action.case_type))

    def uses_usercase(self):
        return self.uses_case_type(USERCASE_TYPE)

    def all_other_forms_require_a_case(self):
        m = self.get_module()
        return all([form.requires == 'case' for form in m.get_forms() if form.id != self.id])

    def get_module(self):
        return self._parent

    def get_phase(self):
        module = self.get_module()

        return next((phase for phase in module.get_schedule_phases()
                     for form in phase.get_forms()
                     if form.unique_id == self.unique_id),
                    None)

    def disable_schedule(self):
        self.schedule.enabled = False
        phase = self.get_phase()
        if phase:
            phase.remove_form(self)

    def check_actions(self):
        errors = []

        for action in self.actions.get_subcase_actions():
            case_tags = self.actions.get_case_tags()
            for case_index in action.case_indices:
                if case_index.tag not in case_tags:
                    errors.append({'type': 'missing parent tag', 'case_tag': case_index.tag})

            if isinstance(action, AdvancedOpenCaseAction):
                if not action.name_path:
                    errors.append({'type': 'case_name required', 'case_tag': action.case_tag})

                for case_index in action.case_indices:
                    meta = self.actions.actions_meta_by_tag.get(case_index.tag)
                    if meta and meta['type'] == 'open' and meta['action'].repeat_context:
                        if (
                            not action.repeat_context or
                            not action.repeat_context.startswith(meta['action'].repeat_context)
                        ):
                            errors.append({'type': 'subcase repeat context',
                                           'case_tag': action.case_tag,
                                           'parent_tag': case_index.tag})

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
            form_filter_references_case = (
                xpath_references_case(self.form_filter) or
                xpath_references_user_case(self.form_filter)
            )

            if form_filter_references_case:
                if not any(action for action in self.actions.load_update_cases if not action.auto_select):
                    errors.append({'type': "filtering without case"})

        def generate_paths():
            for action in self.actions.get_all_actions():
                for path in action.get_paths():
                    yield path

            if self.schedule:
                if self.schedule.transition_condition.type == 'if':
                    yield self.schedule.transition_condition.question
                if self.schedule.termination_condition.type == 'if':
                    yield self.schedule.termination_condition.question

        errors.extend(self.check_paths(generate_paths()))

        return errors

    def extended_build_validation(self, error_meta, xml_valid, validate_module=True):
        errors = []
        if xml_valid:
            for error in self.check_actions():
                error.update(error_meta)
                errors.append(error)

        module = self.get_module()
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
        if self.schedule and self.schedule.enabled and self.source:
            xform = self.wrapped_xform()
            self.add_stuff_to_xform(xform)
            scheduler_updates = xform.get_scheduler_case_updates()[case_type]
        else:
            scheduler_updates = set()

        return updates.union(scheduler_updates)

    @property
    def case_references(self):
        return {}

    @case_references.setter
    def case_references(self, refs):
        pass

    @memoized
    def get_parent_types_and_contributed_properties(self, module_case_type, case_type):
        parent_types = set()
        case_properties = set()
        for subcase in self.actions.get_subcase_actions():
            if subcase.case_type == case_type:
                case_properties.update(
                    subcase.case_properties.keys()
                )
                for case_index in subcase.case_indices:
                    parent = self.actions.get_action_from_tag(case_index.tag)
                    if parent:
                        parent_types.add((parent.case_type, case_index.reference_id or 'parent'))

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


class SchedulePhaseForm(IndexedSchema):
    """
    A reference to a form in a schedule phase.
    """
    form_id = FormIdProperty("modules[*].schedule_phases[*].forms[*].form_id")


class SchedulePhase(IndexedSchema):
    """
    SchedulePhases are attached to a module.
    A Schedule Phase is a grouping of forms that occur within a period and share an anchor
    A module should not have more than one SchedulePhase with the same anchor

    anchor:                     Case property containing a date after which this phase becomes active
    forms: 			The forms that are to be filled out within this phase
    """
    anchor = StringProperty()
    forms = SchemaListProperty(SchedulePhaseForm)

    @property
    def id(self):
        """ A Schedule Phase is 1-indexed """
        _id = super(SchedulePhase, self).id
        return _id + 1

    @property
    def phase_id(self):
        return "{}_{}".format(self.anchor, self.id)

    def get_module(self):
        return self._parent

    _get_forms = IndexedSchema.Getter('forms')

    def get_forms(self):
        """Returns the actual form objects related to this phase"""
        module = self.get_module()
        return (module.get_form_by_unique_id(form.form_id) for form in self._get_forms())

    def get_form(self, desired_form):
        return next((form for form in self.get_forms() if form.unique_id == desired_form.unique_id), None)

    def get_phase_form_index(self, form):
        """
        Returns the index of the form with respect to the phase

        schedule_phase.forms = [a,b,c]
        schedule_phase.get_phase_form_index(b)
        => 1
        schedule_phase.get_phase_form_index(c)
        => 2
        """
        return next((phase_form.id for phase_form in self._get_forms() if phase_form.form_id == form.unique_id),
                    None)

    def remove_form(self, form):
        """Remove a form from the phase"""
        idx = self.get_phase_form_index(form)
        if idx is None:
            raise ScheduleError("That form doesn't exist in the phase")

        self.forms.remove(self.forms[idx])

    def add_form(self, form):
        """Adds a form to this phase, removing it from other phases"""
        old_phase = form.get_phase()
        if old_phase is not None and old_phase.anchor != self.anchor:
            old_phase.remove_form(form)

        if self.get_form(form) is None:
            self.forms.append(SchedulePhaseForm(form_id=form.unique_id))

    def change_anchor(self, new_anchor):
        if new_anchor is None or new_anchor.strip() == '':
            raise ScheduleError(_("You can't create a phase without an anchor property"))

        self.anchor = new_anchor

        if self.get_module().phase_anchors.count(new_anchor) > 1:
            raise ScheduleError(_("You can't have more than one phase with the anchor {}").format(new_anchor))


class AdvancedModule(ModuleBase):
    module_type = 'advanced'
    case_label = DictProperty()
    forms = SchemaListProperty(AdvancedForm)
    case_details = SchemaProperty(DetailPair)
    product_details = SchemaProperty(DetailPair)
    put_in_root = BooleanProperty(default=False)
    case_list = SchemaProperty(CaseList)
    has_schedule = BooleanProperty()
    schedule_phases = SchemaListProperty(SchedulePhase)
    get_schedule_phases = IndexedSchema.Getter('schedule_phases')
    search_config = SchemaProperty(CaseSearch)

    @classmethod
    def wrap(cls, data):
        # lazy migration to accommodate search_config as empty list
        # http://manage.dimagi.com/default.asp?231186
        if data.get('search_config') == []:
            data['search_config'] = {}
        return super(AdvancedModule, cls).wrap(data)

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
        form.schedule = FormSchedule(enabled=False)

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
                    select_chain = get_select_chain(app, from_module, include_self=False)
                    for n, link in enumerate(reversed(list(enumerate(select_chain)))):
                        i, module = link
                        new_form.actions.load_update_cases.append(LoadUpdateAction(
                            case_type=module.case_type,
                            case_tag='_'.join(['parent'] * (i + 1)),
                            details_module=module.unique_id,
                            case_index=CaseIndex(tag='_'.join(['parent'] * (i + 2)) if n > 0 else '')
                        ))

                    base_action.case_indices = [CaseIndex(tag='parent')]

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
                        case_indices=[CaseIndex(
                            tag=base_action.case_tag if base_action else '',
                            reference_id=subcase.reference_id,
                        )]
                    )
                    new_form.actions.open_cases.append(open_subcase_action)
        else:
            raise IncompatibleFormTypeException()

        if index is not None:
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
            loaded_case_types = None
            for form in forms:
                info = self.get_module_info()
                form_info = {"id": form.id if hasattr(form, 'id') else None, "name": form.name}
                non_auto_select_actions = [a for a in form.actions.load_update_cases if not a.auto_select]
                this_forms_loaded_case_types = {action.case_type for action in non_auto_select_actions}
                if loaded_case_types is None:
                    loaded_case_types = this_forms_loaded_case_types
                elif loaded_case_types != this_forms_loaded_case_types:
                    errors.append({
                        'type': 'all forms in case list module must load the same cases',
                        'module': info,
                        'form': form_info,
                    })

                if not non_auto_select_actions:
                    errors.append({
                        'type': 'case list module form must require case',
                        'module': info,
                        'form': form_info,
                    })
                elif len(non_auto_select_actions) != 1:
                    for index, action in reversed(list(enumerate(non_auto_select_actions))):
                        if (
                            index > 0 and
                            non_auto_select_actions[index - 1].case_tag not in (p.tag for p in action.case_indices)
                        ):
                            errors.append({
                                'type': 'case list module form can only load parent cases',
                                'module': info,
                                'form': form_info,
                            })

                case_action = non_auto_select_actions[-1] if non_auto_select_actions else None
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

    def _uses_case_type(self, case_type, invert_match=False):
        return any(form.uses_case_type(case_type, invert_match) for form in self.forms)

    def uses_usercase(self):
        """Return True if this module has any forms that use the usercase.
        """
        return self._uses_case_type(USERCASE_TYPE)

    @property
    def phase_anchors(self):
        return [phase.anchor for phase in self.schedule_phases]

    def get_or_create_schedule_phase(self, anchor):
        """Returns a tuple of (phase, new?)"""
        if anchor is None or anchor.strip() == '':
            raise ScheduleError(_("You can't create a phase without an anchor property"))

        phase = next((phase for phase in self.get_schedule_phases() if phase.anchor == anchor), None)
        is_new_phase = False

        if phase is None:
            self.schedule_phases.append(SchedulePhase(anchor=anchor))
            # TODO: is there a better way of doing this?
            phase = list(self.get_schedule_phases())[-1]  # get the phase from the module so we know the _parent
            is_new_phase = True

        return (phase, is_new_phase)

    def _clear_schedule_phases(self):
        self.schedule_phases = []

    def update_schedule_phases(self, anchors):
        """ Take a list of anchors, reorders, deletes and creates phases from it """
        old_phases = {phase.anchor: phase for phase in self.get_schedule_phases()}
        self._clear_schedule_phases()

        for anchor in anchors:
            try:
                self.schedule_phases.append(old_phases.pop(anchor))
            except KeyError:
                self.get_or_create_schedule_phase(anchor)

        deleted_phases_with_forms = [anchor for anchor, phase in old_phases.iteritems() if len(phase.forms)]
        if deleted_phases_with_forms:
            raise ScheduleError(_("You can't delete phases with anchors "
                                  "{phase_anchors} because they have forms attached to them").format(
                                      phase_anchors=(", ").join(deleted_phases_with_forms)))

        return self.get_schedule_phases()

    def update_schedule_phase_anchors(self, new_anchors):
        """ takes a list of tuples (id, new_anchor) and updates the phase anchors """
        for anchor in new_anchors:
            id = anchor[0] - 1
            new_anchor = anchor[1]
            try:
                list(self.get_schedule_phases())[id].change_anchor(new_anchor)
            except IndexError:
                pass  # That phase wasn't found, so we can't change it's anchor. Ignore it


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

    def add_stuff_to_xform(self, xform, build_profile_id=None):
        super(CareplanForm, self).add_stuff_to_xform(xform, build_profile_id)
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
            if index is not None:
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


class ReportGraphConfig(DocumentSchema):
    graph_type = StringProperty(
        choices=[
            'bar',
            'time',
            'xy',
        ],
        default='bar',
        required=True,
    )
    series_configs = DictProperty(DictProperty)
    config = DictProperty()


class ReportAppFilter(DocumentSchema):

    @classmethod
    def wrap(cls, data):
        if cls is ReportAppFilter:
            return get_report_filter_class_for_doc_type(data['doc_type']).wrap(data)
        else:
            return super(ReportAppFilter, cls).wrap(data)

    def get_filter_value(self, user, ui_filter):
        raise NotImplementedError


MobileFilterConfig = namedtuple('MobileFilterConfig', ['doc_type', 'filter_class', 'short_description'])


def get_all_mobile_filter_configs():
    return [
        MobileFilterConfig('AutoFilter', AutoFilter, _('Value equal to a standard user property')),
        MobileFilterConfig('CustomDataAutoFilter', CustomDataAutoFilter,
                           _('Value equal to a custom user property')),
        MobileFilterConfig('StaticChoiceFilter', StaticChoiceFilter, _('An exact match of a constant value')),
        MobileFilterConfig('StaticChoiceListFilter', StaticChoiceListFilter,
                           _('An exact match of a dynamic property')),
        MobileFilterConfig('StaticDatespanFilter', StaticDatespanFilter, _('A standard date range')),
        MobileFilterConfig('CustomDatespanFilter', CustomDatespanFilter, _('A custom range relative to today')),
        MobileFilterConfig('CustomMonthFilter', CustomMonthFilter,
                           _("Custom Month Filter (you probably don't want this")),
        MobileFilterConfig('MobileSelectFilter', MobileSelectFilter, _('Show choices on mobile device')),
        MobileFilterConfig('AncestorLocationTypeFilter', AncestorLocationTypeFilter,
                           _("Ancestor location of the user's assigned location of a particular type")),
        MobileFilterConfig('NumericFilter', NumericFilter, _('A numeric expression')),
    ]


def get_report_filter_class_for_doc_type(doc_type):
    matched_configs = [config for config in get_all_mobile_filter_configs() if config.doc_type == doc_type]
    if not matched_configs:
        raise ValueError('Unexpected doc_type for ReportAppFilter', doc_type)
    else:
        assert len(matched_configs) == 1
        return matched_configs[0].filter_class


def _filter_by_case_sharing_group_id(user, ui_filter):
    from corehq.apps.reports_core.filters import Choice
    return [
        Choice(value=group._id, display=None)
        for group in user.get_case_sharing_groups()
    ]


def _filter_by_location_id(user, ui_filter):
    return ui_filter.value(**{ui_filter.name: user.location_id})


def _filter_by_username(user, ui_filter):
    from corehq.apps.reports_core.filters import Choice
    return Choice(value=user.raw_username, display=None)


def _filter_by_user_id(user, ui_filter):
    from corehq.apps.reports_core.filters import Choice
    return Choice(value=user._id, display=None)


def _filter_by_parent_location_id(user, ui_filter):
    location = user.sql_location
    location_parent = location.parent.location_id if location and location.parent else None
    return ui_filter.value(**{ui_filter.name: location_parent})


AutoFilterConfig = namedtuple('AutoFilterConfig', ['slug', 'filter_function', 'short_description'])


def get_auto_filter_configurations():
    return [
        AutoFilterConfig('case_sharing_group', _filter_by_case_sharing_group_id,
                         _("The user's case sharing group")),
        AutoFilterConfig('location_id', _filter_by_location_id, _("The user's assigned location")),
        AutoFilterConfig('parent_location_id', _filter_by_parent_location_id,
                         _("The parent location of the user's assigned location")),
        AutoFilterConfig('username', _filter_by_username, _("The user's username")),
        AutoFilterConfig('user_id', _filter_by_user_id, _("The user's ID")),
    ]


def _get_filter_function(slug):
    matched_configs = [config for config in get_all_mobile_filter_configs() if config.slug == slug]
    if not matched_configs:
        raise ValueError('Unexpected ID for AutoFilter', slug)
    else:
        assert len(matched_configs) == 1
        return matched_configs[0].filter_function


class AutoFilter(ReportAppFilter):
    filter_type = StringProperty(choices=[f.slug for f in get_auto_filter_configurations()])

    def get_filter_value(self, user, ui_filter):
        return _get_filter_function(self.filter_type)(user, ui_filter)


class CustomDataAutoFilter(ReportAppFilter):
    custom_data_property = StringProperty()

    def get_filter_value(self, user, ui_filter):
        from corehq.apps.reports_core.filters import Choice
        return Choice(value=user.user_data[self.custom_data_property], display=None)


class StaticChoiceFilter(ReportAppFilter):
    select_value = StringProperty()

    def get_filter_value(self, user, ui_filter):
        from corehq.apps.reports_core.filters import Choice
        return [Choice(value=self.select_value, display=None)]


class StaticChoiceListFilter(ReportAppFilter):
    value = StringListProperty()

    def get_filter_value(self, user, ui_filter):
        from corehq.apps.reports_core.filters import Choice
        return [Choice(value=string_value, display=None) for string_value in self.value]


class StaticDatespanFilter(ReportAppFilter):
    date_range = StringProperty(
        choices=[choice.slug for choice in get_simple_dateranges()],
        required=True,
    )

    def get_filter_value(self, user, ui_filter):
        start_date, end_date = get_daterange_start_end_dates(self.date_range)
        return DateSpan(startdate=start_date, enddate=end_date)


class CustomDatespanFilter(ReportAppFilter):
    operator = StringProperty(
        choices=[
            '=',
            '<=',
            '>=',
            '>',
            '<',
            'between'
        ],
        required=True,
    )
    date_number = StringProperty(required=True)
    date_number2 = StringProperty()

    def get_filter_value(self, user, ui_filter):
        assert user is not None, (
            "CustomDatespanFilter.get_filter_value must be called "
            "with an OTARestoreUser object, not None")

        timezone = get_timezone_for_domain(user.domain)
        today = ServerTime(datetime.datetime.utcnow()).user_time(timezone).done().date()
        start_date = end_date = None
        days = int(self.date_number)
        if self.operator == 'between':
            days2 = int(self.date_number2)
            # allows user to have specified the two numbers in either order
            if days > days2:
                end = days2
                start = days
            else:
                start = days2
                end = days
            start_date = today - datetime.timedelta(days=start)
            end_date = today - datetime.timedelta(days=end)
        elif self.operator == '=':
            start_date = end_date = today - datetime.timedelta(days=days)
        elif self.operator == '>=':
            start_date = None
            end_date = today - datetime.timedelta(days=days)
        elif self.operator == '<=':
            start_date = today - datetime.timedelta(days=days)
            end_date = None
        elif self.operator == '<':
            start_date = today - datetime.timedelta(days=days - 1)
            end_date = None
        elif self.operator == '>':
            start_date = None
            end_date = today - datetime.timedelta(days=days + 1)
        return DateSpan(startdate=start_date, enddate=end_date)


def is_lte(integer):
    def validate(x):
        if not x <= integer:
            raise BadValueError('Value must be less than or equal to {}'.format(integer))
    return validate


def is_gte(integer):
    def validate(x):
        if not x >= integer:
            raise BadValueError('Value must be greater than or equal to {}'.format(integer))
    return validate


class CustomMonthFilter(ReportAppFilter):
    """
    Filter by months that start on a day number other than 1

    See [FB 215656](http://manage.dimagi.com/default.asp?215656)
    """
    # Values for start_of_month < 1 specify the number of days from the end of the month. Values capped at
    # len(February).
    start_of_month = IntegerProperty(
        required=True,
        validators=(is_gte(-27), is_lte(28))
    )
    # DateSpan to return i.t.o. number of months to go back
    period = IntegerProperty(
        default=DEFAULT_MONTH_FILTER_PERIOD_LENGTH,
        validators=(is_gte(0),)
    )

    @classmethod
    def wrap(cls, doc):
        doc['start_of_month'] = int(doc['start_of_month'])
        if 'period' in doc:
            doc['period'] = int(doc['period'] or DEFAULT_MONTH_FILTER_PERIOD_LENGTH)
        return super(CustomMonthFilter, cls).wrap(doc)

    def get_filter_value(self, user, ui_filter):
        def get_last_month(this_month):
            return datetime.date(this_month.year, this_month.month, 1) - datetime.timedelta(days=1)

        def get_last_day(date):
            _, last_day = calendar.monthrange(date.year, date.month)
            return last_day

        start_of_month = int(self.start_of_month)
        today = datetime.date.today()
        if start_of_month > 0:
            start_day = start_of_month
        else:
            # start_of_month is zero or negative. Work backwards from the end of the month
            start_day = get_last_day(today) + start_of_month

        # Loop over months backwards for period > 0
        month = today if today.day >= start_day else get_last_month(today)
        for i in range(int(self.period)):
            month = get_last_month(month)

        if start_of_month > 0:
            start_date = datetime.date(month.year, month.month, start_day)
            days = get_last_day(start_date) - 1
            end_date = start_date + datetime.timedelta(days=days)
        else:
            start_day = get_last_day(month) + start_of_month
            start_date = datetime.date(month.year, month.month, start_day)
            next_month = datetime.date(month.year, month.month, get_last_day(month)) + datetime.timedelta(days=1)
            end_day = get_last_day(next_month) + start_of_month - 1
            end_date = datetime.date(next_month.year, next_month.month, end_day)

        return DateSpan(startdate=start_date, enddate=end_date)


class MobileSelectFilter(ReportAppFilter):

    def get_filter_value(self, user, ui_filter):
        return None


class AncestorLocationTypeFilter(ReportAppFilter):
    ancestor_location_type_name = StringProperty()

    def get_filter_value(self, user, ui_filter):
        from corehq.apps.locations.models import SQLLocation

        try:
            ancestor = user.sql_location.get_ancestors(include_self=True).\
                get(location_type__name=self.ancestor_location_type_name)
        except (AttributeError, SQLLocation.DoesNotExist):
            # user.sql_location is None, or location does not have an ancestor of that type
            return None
        return ancestor.location_id


class NumericFilter(ReportAppFilter):
    operator = StringProperty(choices=['=', '!=', '<', '<=', '>', '>=']),
    operand = FloatProperty()

    @classmethod
    def wrap(cls, doc):
        doc['operand'] = float(doc['operand'])
        return super(NumericFilter, cls).wrap(doc)

    def get_filter_value(self, user, ui_filter):
        return {
            'operator': self.operator,
            'operand': self.operand,
        }


class ReportAppConfig(DocumentSchema):
    """
    Class for configuring how a user configurable report shows up in an app
    """
    report_id = StringProperty(required=True)
    header = DictProperty()
    localized_description = DictProperty()
    xpath_description = StringProperty()
    use_xpath_description = BooleanProperty(default=False)
    graph_configs = DictProperty(ReportGraphConfig)
    filters = SchemaDictProperty(ReportAppFilter)
    uuid = StringProperty(required=True)

    _report = None

    def __init__(self, *args, **kwargs):
        super(ReportAppConfig, self).__init__(*args, **kwargs)
        if not self.uuid:
            self.uuid = random_hex()

    @classmethod
    def wrap(cls, doc):
        # for backwards compatibility with apps that have localized or xpath descriptions
        old_description = doc.get('description')
        if old_description:
            if isinstance(old_description, basestring) and not doc.get('xpath_description'):
                doc['xpath_description'] = old_description
            elif isinstance(old_description, dict) and not doc.get('localized_description'):
                doc['localized_description'] = old_description
        if not doc.get('xpath_description'):
            doc['xpath_description'] = '""'

        return super(ReportAppConfig, cls).wrap(doc)

    def report(self, domain):
        if self._report is None:
            from corehq.apps.userreports.models import get_report_config
            self._report = get_report_config(self.report_id, domain)[0]
        return self._report


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
        from corehq.apps.userreports.models import get_report_configs
        return get_report_configs([r.report_id for r in self.report_configs], self.get_app().domain)

    @classmethod
    def new_module(cls, name, lang):
        module = ReportModule(
            name={(lang or 'en'): name or ugettext("Reports")},
            case_type='',
        )
        module.get_or_create_unique_id()
        return module

    def get_details(self):
        from .suite_xml.features.mobile_ucr import ReportModuleSuiteHelper
        return ReportModuleSuiteHelper(self).get_details()

    def get_custom_entries(self):
        from .suite_xml.features.mobile_ucr import ReportModuleSuiteHelper
        return ReportModuleSuiteHelper(self).get_custom_entries()

    def get_menus(self, supports_module_filter=False):
        kwargs = {}
        if supports_module_filter:
            kwargs['relevant'] = interpolate_xpath(self.module_filter)

        menu = suite_models.LocalizedMenu(
            id=id_strings.menu_id(self),
            menu_locale_id=id_strings.module_locale(self),
            media_image=bool(len(self.all_image_paths())),
            media_audio=bool(len(self.all_audio_paths())),
            image_locale_id=id_strings.module_icon_locale(self),
            audio_locale_id=id_strings.module_audio_locale(self),
            **kwargs
        )
        menu.commands.extend([
            suite_models.Command(id=id_strings.report_command(config.uuid))
            for config in self.report_configs
        ])
        yield menu

    def check_report_validity(self):
        """
        returns is_valid, valid_report_configs

        If any report doesn't exist, is_valid is False, otherwise True
        valid_report_configs is a list of all report configs that refer to existing reports

        """
        try:
            all_report_ids = [report._id for report in self.reports]
            valid_report_configs = [report_config for report_config in self.report_configs
                                    if report_config.report_id in all_report_ids]
            is_valid = (len(valid_report_configs) == len(self.report_configs))
        except ReportConfigurationNotFoundError:
            valid_report_configs = []  # assuming that if one report is in a different domain, they all are
            is_valid = False

        return namedtuple('ReportConfigValidity', 'is_valid valid_report_configs')(
            is_valid=is_valid,
            valid_report_configs=valid_report_configs
        )

    def validate_for_build(self):
        errors = super(ReportModule, self).validate_for_build()
        if not self.check_report_validity().is_valid:
            errors.append({
                'type': 'report config ref invalid',
                'module': self.get_module_info()
            })
        return errors


class ShadowModule(ModuleBase, ModuleDetailsMixin):
    """
    A module that acts as a shortcut to another module. This module has its own
    settings (name, icon/audio, filter, etc.) and its own case list/detail, but
    inherits case type and forms from its source module.
    """
    module_type = 'shadow'
    source_module_id = StringProperty()
    forms = []
    excluded_form_ids = SchemaListProperty()
    case_details = SchemaProperty(DetailPair)
    ref_details = SchemaProperty(DetailPair)
    put_in_root = BooleanProperty(default=False)
    case_list = SchemaProperty(CaseList)
    referral_list = SchemaProperty(CaseList)
    task_list = SchemaProperty(CaseList)
    parent_select = SchemaProperty(ParentSelect)

    get_forms = IndexedSchema.Getter('forms')

    @classmethod
    def wrap(cls, data):
        data = cls.wrap_details(data)
        return super(ShadowModule, cls).wrap(data)

    @property
    def source_module(self):
        if self.source_module_id:
            try:
                return self._parent.get_module_by_unique_id(self.source_module_id,
                       error=_("Could not find source module for '{}'.").format(self.default_name()))
            except ModuleNotFoundException:
                pass
        return None

    @property
    def case_type(self):
        if not self.source_module:
            return None
        return self.source_module.case_type

    @property
    def requires(self):
        if not self.source_module:
            return 'none'
        return self.source_module.requires

    @property
    def root_module_id(self):
        if not self.source_module:
            return None
        return self.source_module.root_module_id

    def get_suite_forms(self):
        if not self.source_module:
            return []
        return [f for f in self.source_module.get_forms() if f.unique_id not in self.excluded_form_ids]

    @parse_int([1])
    def get_form(self, i):
        return None

    def requires_case_details(self):
        if not self.source_module:
            return False
        return self.source_module.requires_case_details()

    def get_case_types(self):
        if not self.source_module:
            return []
        return self.source_module.get_case_types()

    @memoized
    def get_subcase_types(self):
        if not self.source_module:
            return []
        return self.source_module.get_subcase_types()

    @memoized
    def all_forms_require_a_case(self):
        if not self.source_module:
            return []
        return self.source_module.all_forms_require_a_case()

    @classmethod
    def new_module(cls, name, lang):
        lang = lang or 'en'
        detail = Detail(
            columns=[DetailColumn(
                format='plain',
                header={(lang or 'en'): ugettext("Name")},
                field='name',
                model='case',
            )]
        )
        module = ShadowModule(
            name={(lang or 'en'): name or ugettext("Untitled Module")},
            case_details=DetailPair(
                short=Detail(detail.to_json()),
                long=Detail(detail.to_json()),
            ),
        )
        module.get_or_create_unique_id()
        return module

    def validate_for_build(self):
        errors = super(ShadowModule, self).validate_for_build()
        errors += self.validate_details_for_build()
        if not self.source_module:
            errors.append({
                'type': 'no source module id',
                'module': self.get_module_info()
            })
        return errors


class LazyBlobDoc(BlobMixin):
    """LazyAttachmentDoc for blob db

    Cache blobs in local memory (for this request)
    and in django cache (for the next few requests)
    and commit to couchdb.

    See also `dimagi.utils.couch.lazy_attachment_doc.LazyAttachmentDoc`

    Cache strategy:
    - on fetch, check in local memory, then cache
      - if both are a miss, fetch from couchdb and store in both
    - after an attachment is committed to the blob db and the
      save save has succeeded, save the attachment in the cache
    """

    def __init__(self, *args, **kwargs):
        super(LazyBlobDoc, self).__init__(*args, **kwargs)
        self._LAZY_ATTACHMENTS = {}
        # to cache fetched attachments
        # these we do *not* send back down upon save
        self._LAZY_ATTACHMENTS_CACHE = {}

    @classmethod
    def wrap(cls, data):
        if "_attachments" in data:
            data = data.copy()
            attachments = data.pop("_attachments").copy()
            if cls.migrating_blobs_from_couch:
                # preserve stubs so couch attachments don't get deleted on save
                stubs = {}
                for name, value in list(attachments.items()):
                    if isinstance(value, dict) and "stub" in value:
                        stubs[name] = attachments.pop(name)
                if stubs:
                    data["_attachments"] = stubs
        else:
            attachments = None
        self = super(LazyBlobDoc, cls).wrap(data)
        if attachments:
            for name, attachment in attachments.items():
                if isinstance(attachment, basestring):
                    info = {"content": attachment}
                else:
                    raise ValueError("Unknown attachment format: {!r}"
                                     .format(attachment))
                self.lazy_put_attachment(name=name, **info)
        return self

    def __attachment_cache_key(self, name):
        return u'lazy_attachment/{id}/{name}'.format(id=self.get_id, name=name)

    def __set_cached_attachment(self, name, content, timeout=60*60*24):
        cache.set(self.__attachment_cache_key(name), content, timeout=timeout)
        self._LAZY_ATTACHMENTS_CACHE[name] = content

    def __get_cached_attachment(self, name):
        try:
            # it has been fetched already during this request
            content = self._LAZY_ATTACHMENTS_CACHE[name]
        except KeyError:
            content = cache.get(self.__attachment_cache_key(name))
            if content is not None:
                self._LAZY_ATTACHMENTS_CACHE[name] = content
        return content

    def put_attachment(self, content, name=None, *args, **kw):
        cache.delete(self.__attachment_cache_key(name))
        self._LAZY_ATTACHMENTS_CACHE.pop(name, None)
        return super(LazyBlobDoc, self).put_attachment(content, name, *args, **kw)

    def has_attachment(self, name):
        return name in self.lazy_list_attachments()

    def lazy_put_attachment(self, content, name=None, content_type=None,
                            content_length=None):
        """
        Ensure the attachment is available through lazy_fetch_attachment
        and that upon self.save(), the attachments are put to the doc as well

        """
        self._LAZY_ATTACHMENTS[name] = {
            'content': content,
            'content_type': content_type,
            'content_length': content_length,
        }

    def lazy_fetch_attachment(self, name):
        # it has been put/lazy-put already during this request
        if name in self._LAZY_ATTACHMENTS:
            content = self._LAZY_ATTACHMENTS[name]['content']
        else:
            content = self.__get_cached_attachment(name)

            if content is None:
                try:
                    content = self.fetch_attachment(name)
                except ResourceNotFound as e:
                    # django cache will pickle this exception for you
                    # but e.response isn't picklable
                    if hasattr(e, 'response'):
                        del e.response
                    content = e
                    self.__set_cached_attachment(name, content, timeout=60*5)
                    raise
                else:
                    self.__set_cached_attachment(name, content)

        if isinstance(content, ResourceNotFound):
            raise content

        return content

    def lazy_list_attachments(self):
        keys = set()
        keys.update(getattr(self, '_LAZY_ATTACHMENTS', None) or {})
        keys.update(self.blobs or {})
        return keys

    def save(self, **params):
        def super_save():
            super(LazyBlobDoc, self).save(**params)
        if self._LAZY_ATTACHMENTS:
            with self.atomic_blobs(super_save):
                for name, info in self._LAZY_ATTACHMENTS.items():
                    if not info['content_type']:
                        info['content_type'] = ';'.join(filter(None, guess_type(name)))
                    super(LazyBlobDoc, self).put_attachment(name=name, **info)
            # super_save() has succeeded by now
            for name, info in self._LAZY_ATTACHMENTS.items():
                self.__set_cached_attachment(name, info['content'])
            self._LAZY_ATTACHMENTS.clear()
        else:
            super_save()


class VersionedDoc(LazyBlobDoc):
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
            bad_keys = ('_id', '_rev', '_attachments', 'external_blobs',
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
        app.pop('_attachments', None)
        app.pop('external_blobs', None)
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
        return source

    def export_json(self, dump_json=True):
        source = deepcopy(self.to_json())
        for field in self._meta_fields:
            if field in source:
                del source[field]
        _attachments = {}
        for name in self.lazy_list_attachments():
            if re.match(ATTACHMENT_REGEX, name):
                # FIXME loss of metadata (content type, etc.)
                _attachments[name] = self.lazy_fetch_attachment(name)

        # the '_attachments' value is a dict of `name: blob_content`
        # pairs, and is part of the exported (serialized) app interface
        source['_attachments'] = _attachments
        source.pop("external_blobs", None)
        source = self.scrub_source(source)

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


class BuildProfile(DocumentSchema):
    name = StringProperty()
    langs = StringListProperty()

    def __eq__(self, other):
        return self.langs == other.langs

    def __ne__(self, other):
        return not self.__eq__(other)


class MediaList(DocumentSchema):
    media_refs = StringListProperty()


class ApplicationBase(VersionedDoc, SnapshotMixin,
                      CommCareFeatureSupportMixin,
                      CommentMixin):
    """
    Abstract base class for Application and RemoteApp.
    Contains methods for generating the various files and zipping them into CommCare.jar

    See note at top of file for high-level overview.
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

    langs = StringListProperty()

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
    minimum_use_threshold = StringProperty(
        default='15'
    )
    experienced_threshold = StringProperty(
        default='3'
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
    vellum_case_management = BooleanProperty(default=False)

    build_profiles = SchemaDictProperty(BuildProfile)

    # each language is a key and the value is a list of multimedia referenced in that language
    media_language_map = SchemaDictProperty(MediaList)

    use_j2me_endpoint = BooleanProperty(default=False)

    # Whether or not the Application has had any forms submitted against it
    has_submissions = BooleanProperty(default=False)

    # domains that are allowed to have linked apps with this master
    linked_whitelist = StringListProperty()

    @classmethod
    def wrap(cls, data):
        should_save = False
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

        if 'build_langs' in data:
            if data['build_langs'] != data['langs'] and 'build_profiles' not in data:
                data['build_profiles'] = {
                    uuid.uuid4().hex: dict(
                        name=', '.join(data['build_langs']),
                        langs=data['build_langs']
                    )
                }
                should_save = True
            del data['build_langs']

        if 'original_doc' in data:
            data['copy_history'] = [data.pop('original_doc')]
            should_save = True

        data["description"] = data.get('description') or data.get('short_description')

        self = super(ApplicationBase, cls).wrap(data)
        if not self.build_spec or self.build_spec.is_null():
            self.build_spec = get_default_build_spec()

        if should_save:
            self.save()

        return self

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

    @memoized
    def get_latest_saved(self):
        """
        This looks really similar to get_latest_app, not sure why tim added
        """
        doc = (get_latest_released_app_doc(self.domain, self._id) or
               get_latest_build_doc(self.domain, self._id))
        return self.__class__.wrap(doc) if doc else None

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

    @property
    def commcare_minor_release(self):
        """This is mostly just for views"""
        return '%d.%d' % self.build_spec.minor_release()

    @property
    def short_name(self):
        return self.name if len(self.name) <= 12 else '%s..' % self.name[:10]

    @property
    def has_careplan_module(self):
        return False

    @property
    def url_base(self):
        custom_base_url = getattr(self, 'custom_base_url', None)
        return custom_base_url or get_url_base()

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
        return reverse('app_aware_restore', args=[self.domain, self._id])

    @absolute_url_property
    def form_record_url(self):
        return '/a/%s/api/custom/pact_formdata/v1/' % self.domain

    @absolute_url_property
    def hq_profile_url(self):
        # RemoteApp already has a property called "profile_url",
        # Application.profile_url just points here to stop the conflict
        # http://manage.dimagi.com/default.asp?227088#1149422
        return "%s?latest=true" % (
            reverse('download_profile', args=[self.domain, self._id])
        )

    @absolute_url_property
    def media_profile_url(self):
        return "%s?latest=true" % (
            reverse('download_media_profile', args=[self.domain, self._id])
        )

    @property
    def profile_loc(self):
        return "jr://resource/profile.xml"

    @absolute_url_property
    def jar_url(self):
        return reverse('download_jar', args=[self.domain, self._id])

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
        return self.get_build().get_jadjar(self.get_jar_path(), self.use_j2me_endpoint)

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

    def validate_intents(self):
        if domain_has_privilege(self.domain, privileges.CUSTOM_INTENTS):
            return

        if hasattr(self, 'get_forms'):
            for form in self.get_forms():
                intents = form.wrapped_xform().odk_intents
                if intents:
                    if not domain_has_privilege(self.domain, privileges.TEMPLATED_INTENTS):
                        raise PermissionDenied(_(
                            "Usage of integrations is not supported by your "
                            "current subscription. Please upgrade your "
                            "subscription before using this feature."
                        ))
                    else:
                        templates = next(app_callout_templates)
                        if len(set(intents) - set(t['id'] for t in templates)):
                            raise PermissionDenied(_(
                                "Usage of external integration is not supported by your "
                                "current subscription. Please upgrade your "
                                "subscription before using this feature."
                            ))

    def validate_jar_path(self):
        build = self.get_build()
        setting = commcare_settings.get_commcare_settings_lookup()['hq']['text_input']
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
    def advanced_app_builder(self):
        properties = (self.profile or {}).get('properties', {})
        return properties.get('advanced_app_builder', 'false') == 'true'

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

    def create_build_files(self, save=False, build_profile_id=None):
        built_on = datetime.datetime.utcnow()
        all_files = self.create_all_files(build_profile_id)
        if save:
            self.date_created = built_on
            self.built_on = built_on
            self.built_with = BuildRecord(
                version=self.build_spec.version,
                build_number=self.version,
                datetime=built_on,
            )

            for filepath in all_files:
                self.lazy_put_attachment(all_files[filepath],
                                         'files/%s' % filepath)

    def create_jadjar_from_build_files(self, save=False):
        self.validate_jar_path()
        with CriticalSection(['create_jadjar_' + self._id]):
            try:
                return (
                    self.lazy_fetch_attachment('CommCare.jad'),
                    self.lazy_fetch_attachment('CommCare.jar'),
                )
            except (ResourceError, KeyError):
                all_files = {
                    filename[len('files/'):]: self.lazy_fetch_attachment(filename)
                    for filename in self.blobs if filename.startswith('files/')
                }
                all_files = {
                    name: (contents if isinstance(contents, str) else contents.encode('utf-8'))
                    for name, contents in all_files.items()
                }
                release_date = self.built_with.datetime or datetime.datetime.utcnow()
                jad_settings = {
                    'Released-on': release_date.strftime("%Y-%b-%d %H:%M"),
                }
                jad_settings.update(self.jad_settings)
                jadjar = self.get_jadjar().pack(all_files, jad_settings)

                if save:
                    self.lazy_put_attachment(jadjar.jad, 'CommCare.jad')
                    self.lazy_put_attachment(jadjar.jar, 'CommCare.jar')
                    self.built_with.signed = jadjar.signed

                return jadjar.jad, jadjar.jar

    def validate_app(self):
        errors = []

        errors.extend(self.check_password_charset())

        try:
            self.validate_fixtures()
            self.validate_intents()
            self.create_all_files()
        except CaseXPathValidationError as cve:
            errors.append({
                'type': 'invalid case xpath reference',
                'module': cve.module,
                'form': cve.form,
            })
        except UserCaseXPathValidationError as ucve:
            errors.append({
                'type': 'invalid user case xpath reference',
                'module': ucve.module,
                'form': ucve.form,
            })
        except (AppEditingError, XFormValidationError, XFormException,
                PermissionDenied, SuiteValidationError) as e:
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
        return reverse('download_odk_profile', args=[self.domain, self._id])

    @absolute_url_property
    def odk_media_profile_url(self):
        return reverse('download_odk_media_profile', args=[self.domain, self._id])

    @property
    def odk_profile_display_url(self):
        return self.short_odk_url or self.odk_profile_url

    @property
    def odk_media_profile_display_url(self):
        return self.short_odk_media_url or self.odk_media_profile_url

    def get_odk_qr_code(self, with_media=False, build_profile_id=None):
        """Returns a QR code, as a PNG to install on CC-ODK"""
        try:
            return self.lazy_fetch_attachment("qrcode.png")
        except ResourceNotFound:
            from pygooglechart import QRChart
            HEIGHT = WIDTH = 250
            code = QRChart(HEIGHT, WIDTH)
            url = self.odk_profile_url if not with_media else self.odk_media_profile_url
            if build_profile_id is not None:
                url += '?profile={profile_id}'.format(profile_id=build_profile_id)
            code.add_data(url)

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

    def generate_shortened_url(self, view_name, build_profile_id=None):
        try:
            if settings.BITLY_LOGIN:
                if build_profile_id is not None:
                    long_url = "{}{}?profile={}".format(
                        self.url_base, reverse(view_name, args=[self.domain, self._id]), build_profile_id
                    )
                else:
                    long_url = "{}{}".format(self.url_base, reverse(view_name, args=[self.domain, self._id]))
                shortened_url = bitly.shorten(long_url)
            else:
                shortened_url = None
        except Exception:
            logging.exception("Problem creating bitly url for app %s. Do you have network?" % self.get_id)
        else:
            return shortened_url

    def get_short_url(self, build_profile_id=None):
        if not build_profile_id:
            if not self.short_url:
                self.short_url = self.generate_shortened_url('download_jad')
                self.save()
            return self.short_url
        else:
            return self.generate_shortened_url('download_jad', build_profile_id)

    def get_short_odk_url(self, with_media=False, build_profile_id=None):
        if not build_profile_id:
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
        else:
            if with_media:
                return self.generate_shortened_url('download_odk_media_profile', build_profile_id)
            else:
                return self.generate_shortened_url('download_odk_profile', build_profile_id)

    def fetch_jar(self):
        return self.get_jadjar().fetch_jar()

    def make_build(self, comment=None, user_id=None, previous_version=None):
        copy = super(ApplicationBase, self).make_build()
        if not copy._id:
            # I expect this always to be the case
            # but check explicitly so as not to change the _id if it exists
            copy._id = copy.get_db().server.next_uuid()

        force_new_forms = False
        if previous_version and self.build_profiles != previous_version.build_profiles:
            force_new_forms = True
        copy.set_form_versions(previous_version, force_new_forms)
        copy.set_media_versions(previous_version)
        copy.create_build_files(save=True)

        # since this hard to put in a test
        # I'm putting this assert here if copy._id is ever None
        # which makes tests error
        assert copy._id

        copy.build_comment = comment
        copy.comment_from = user_id
        if user_id:
            user = CouchUser.get(user_id)
            if not user.has_built_app:
                user.has_built_app = True
                user.save()
        copy.is_released = False

        if not copy.is_remote_app():
            copy.update_mm_map()

        return copy

    def delete_app(self):
        domain_has_apps.clear(self.domain)
        self.doc_type += '-Deleted'
        record = DeleteApplicationRecord(
            domain=self.domain,
            app_id=self.id,
            datetime=datetime.datetime.utcnow()
        )
        record.save()
        return record

    def save(self, response_json=None, increment_version=None, **params):
        if not self._rev and not domain_has_apps(self.domain):
            domain_has_apps.clear(self.domain)
        user = getattr(view_utils.get_request(), 'couch_user', None)
        if user and user.days_since_created == 0:
            track_workflow(user.get_email(), 'Saved the App Builder within first 24 hours')
        super(ApplicationBase, self).save(
            response_json=response_json, increment_version=increment_version, **params)

    def set_form_versions(self, previous_version, force_new_version=False):
        # by default doing nothing here is fine.
        pass

    def set_media_versions(self, previous_version):
        pass

    def update_mm_map(self):
        if self.build_profiles and domain_has_privilege(self.domain, privileges.BUILD_PROFILES):
            for lang in self.langs:
                self.media_language_map[lang] = MediaList()
            for form in self.get_forms():
                xml = form.wrapped_xform()
                for lang in self.langs:
                    media = []
                    for path in xml.all_media_references(lang):
                        if path is not None:
                            media.append(path)
                            map_item = self.multimedia_map.get(path)
                            #dont break if multimedia is missing
                            if map_item:
                                map_item.form_media = True
                    self.media_language_map[lang].media_refs.extend(media)
        else:
            self.media_language_map = {}

    def get_build_langs(self, build_profile_id=None):
        if build_profile_id is not None:
            return self.build_profiles[build_profile_id].langs
        else:
            return self.langs

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
        for key in ('modules', 'user_registration', 'external_blobs',
                    '_attachments', 'profile', 'translations'
                    'description', 'short_description'):
            data.pop(key, None)
        built_on_user_time = ServerTime(self.built_on).user_time(timezone)
        data.update({
            'id': self.id,
            'built_on_date': built_on_user_time.ui_string(USER_DATE_FORMAT),
            'built_on_time': built_on_user_time.ui_string(USER_TIME_FORMAT),
            'menu_item_label': self.built_with.get_menu_item_label(),
            'jar_path': self.get_jar_path(),
            'short_name': self.short_name,
            'enable_offline_install': self.enable_offline_install,
        })
        comment_from = data['comment_from']
        if comment_from:
            data['comment_user_name'] = get_display_name_for_user_id(
                self.domain, comment_from, default=comment_from)

        return data


class Application(ApplicationBase, TranslationMixin, HQMediaMixin):
    """
    An Application that can be created entirely through the online interface

    """
    modules = SchemaListProperty(ModuleBase)
    name = StringProperty()
    # profile's schema is {'features': {}, 'properties': {}, 'custom_properties': {}}
    # ended up not using a schema because properties is a reserved word
    profile = DictProperty()
    use_custom_suite = BooleanProperty(default=False)
    custom_base_url = StringProperty()
    cloudcare_enabled = BooleanProperty(default=False)
    translation_strategy = StringProperty(default='select-known',
                                          choices=app_strings.CHOICES.keys())
    commtrack_requisition_mode = StringProperty(choices=CT_REQUISITION_MODES)
    auto_gps_capture = BooleanProperty(default=False)
    date_created = DateTimeProperty()
    created_from_template = StringProperty()
    use_grid_menus = BooleanProperty(default=False)
    grid_form_menus = StringProperty(default='none',
                                     choices=['none', 'all', 'some'])

    # legacy property; kept around to be able to identify (deprecated) v1 apps
    application_version = StringProperty(default=APP_V2, choices=[APP_V1, APP_V2], required=False)

    def assert_app_v2(self):
        assert self.application_version == APP_V2

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
        return self.langs[0] if len(self.langs) > 0 else "en"

    def fetch_xform(self, module_id=None, form_id=None, form=None, build_profile_id=None):
        if not form:
            form = self.get_module(module_id).get_form(form_id)
        return form.validate_form().render_xform(build_profile_id).encode('utf-8')

    def set_form_versions(self, previous_version, force_new_version=False):
        """
        Set the 'version' property on each form as follows to the current app version if the form is new
        or has changed since the last build. Otherwise set it to the version from the last build.
        """
        def _hash(val):
            return hashlib.md5(val).hexdigest()

        if previous_version:
            for form_stuff in self.get_forms(bare=False):
                filename = 'files/%s' % self.get_form_filename(**form_stuff)
                form = form_stuff["form"]
                if not force_new_version:
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
                else:
                    form.version = None

    def set_media_versions(self, previous_version):
        """
        Set the media version numbers for all media in the app to the current app version
        if the media is new or has changed since the last build. Otherwise set it to the
        version from the last build.
        """

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

    def create_app_strings(self, lang, build_profile_id=None):
        gen = app_strings.CHOICES[self.translation_strategy]
        if lang == 'default':
            return gen.create_default_app_strings(self, build_profile_id)
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

    def create_profile(self, is_odk=False, with_media=False,
                       template='app_manager/profile.xml', build_profile_id=None):
        self__profile = self.profile
        app_profile = defaultdict(dict)

        for setting in commcare_settings.get_custom_commcare_settings():
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

        locale = self.get_build_langs(build_profile_id)[0]
        return render_to_string(template, {
            'is_odk': is_odk,
            'app': self,
            'profile_url': profile_url,
            'app_profile': app_profile,
            'cc_user_domain': cc_user_domain(self.domain),
            'include_media_suite': with_media,
            'uniqueid': self.copy_of or self.id,
            'name': self.name,
            'descriptor': u"Profile File",
            'build_profile_id': build_profile_id,
            'locale': locale
        }).encode('utf-8')

    @property
    def custom_suite(self):
        try:
            return self.lazy_fetch_attachment('custom_suite.xml')
        except ResourceNotFound:
            return ""

    def set_custom_suite(self, value):
        self.put_attachment(value, 'custom_suite.xml')

    def create_suite(self, build_profile_id=None):
        self.assert_app_v2()
        return SuiteGenerator(self, build_profile_id).generate_suite()

    def create_media_suite(self, build_profile_id=None):
        return MediaSuiteGenerator(self, build_profile_id).generate_suite()

    @classmethod
    def get_form_filename(cls, type=None, form=None, module=None):
        return 'modules-%s/forms-%s.xml' % (module.id, form.id)

    def create_all_files(self, build_profile_id=None):
        prefix = '' if not build_profile_id else build_profile_id + '/'
        files = {
            '{}profile.xml'.format(prefix): self.create_profile(is_odk=False, build_profile_id=build_profile_id),
            '{}profile.ccpr'.format(prefix): self.create_profile(is_odk=True, build_profile_id=build_profile_id),
            '{}media_profile.xml'.format(prefix):
                self.create_profile(is_odk=False, with_media=True, build_profile_id=build_profile_id),
            '{}media_profile.ccpr'.format(prefix):
                self.create_profile(is_odk=True, with_media=True, build_profile_id=build_profile_id),
            '{}suite.xml'.format(prefix): self.create_suite(build_profile_id),
            '{}media_suite.xml'.format(prefix): self.create_media_suite(build_profile_id),
        }

        langs_for_build = self.get_build_langs(build_profile_id)
        for lang in ['default'] + langs_for_build:
            files["{prefix}{lang}/app_strings.txt".format(
                prefix=prefix, lang=lang)] = self.create_app_strings(lang, build_profile_id)
        for form_stuff in self.get_forms(bare=False):
            filename = prefix + self.get_form_filename(**form_stuff)
            form = form_stuff['form']
            try:
                files[filename] = self.fetch_xform(form=form, build_profile_id=build_profile_id)
            except XFormValidationFailed:
                raise XFormException(_('Unable to validate the forms due to a server error. '
                                       'Please try again later.'))
            except XFormException as e:
                raise XFormException(_('Error in form "{}": {}').format(trans(form.name), unicode(e)))
        return files

    get_modules = IndexedSchema.Getter('modules')

    @parse_int([1])
    def get_module(self, i):
        try:
            return self.modules[i].with_id(i % len(self.modules), self)
        except IndexError:
            raise ModuleNotFoundException()

    def get_module_by_unique_id(self, unique_id, error=''):
        def matches(module):
            return module.get_or_create_unique_id() == unique_id
        for obj in self.get_modules():
            if matches(obj):
                return obj
        if not error:
            error = _("Could not find '{unique_id}' in app '{app_id}'.").format(
                app_id=self.id, unique_id=unique_id)
        raise ModuleNotFoundException(error)

    def get_forms(self, bare=True):
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
    def new_app(cls, domain, name, lang="en"):
        app = cls(domain=domain, modules=[], name=name, langs=[lang],
                  date_created=datetime.datetime.utcnow(), vellum_case_management=True)
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
            datetime=datetime.datetime.utcnow()
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
            datetime=datetime.datetime.utcnow(),
        )
        record.save()

        try:
            form.pre_delete_hook()
        except NotImplementedError:
            pass

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
        for profile in self.build_profiles:
            for i, lang in enumerate(profile.langs):
                if lang == old_lang:
                    profile.langs[i] = new_lang
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
            from_module.forms[j].pre_move_hook(from_module, to_module)
        except NotImplementedError:
            pass
        try:
            form = from_module.forms.pop(j)
            if toggles.APP_MANAGER_V2.enabled(self.domain):
                if not to_module.is_surveys and i == 0:
                    # first form is the reg form
                    i = 1
                if from_module.is_surveys != to_module.is_surveys:
                    if from_module.is_surveys:
                        form.requires = "case"
                        form.actions.update_case = UpdateCaseAction(
                            condition=FormActionCondition(type='always'))
                    else:
                        form.requires = "none"
                        form.actions.update_case = UpdateCaseAction(
                            condition=FormActionCondition(type='never'))
            to_module.add_insert_form(from_module, form, index=i, with_source=True)
        except IndexError:
            raise RearrangeError()
        if to_module.case_type != from_module.case_type \
                and not toggles.APP_MANAGER_V2.enabled(self.domain):
            raise ConflictingCaseTypeError()

    def scrub_source(self, source):
        return update_unique_ids(source)

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

        if from_module['case_type'] != to_module['case_type']:
            raise ConflictingCaseTypeError()

        copy_source = deepcopy(form.to_json())
        if 'unique_id' in copy_source:
            del copy_source['unique_id']

        if 'rename' in kwargs and kwargs['rename']:
            for lang, name in copy_source['name'].iteritems():
                with override(lang):
                    copy_source['name'][lang] = _('Copy of {name}').format(name=name)

        copy_form = to_module.add_insert_form(from_module, FormBase.wrap(copy_source))
        save_xform(self, copy_form, form.source)

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

    def check_subscription(self):

        def app_uses_usercase(app):
            return any(m.uses_usercase() for m in app.get_modules())

        errors = []
        if app_uses_usercase(self) and not domain_has_privilege(self.domain, privileges.USER_CASE):
            errors.append({
                'type': 'subscription',
                'message': _('Your application is using User Case functionality. You can remove User Case '
                             'functionality by opening the User Case Management tab in a form that uses it, and '
                             'clicking "Remove User Case Properties".')
            })
        return errors

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
        errors.extend(self.check_subscription())

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

    def get_profile_setting(self, s_type, s_id):
        setting = self.profile.get(s_type, {}).get(s_id)
        if setting is not None:
            return setting
        yaml_setting = commcare_settings.get_commcare_settings_lookup()[s_type][s_id]
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

    def get_subcase_types(self, case_type):
        """
        Return the subcase types defined across an app for the given case type
        """
        return {t for m in self.get_modules()
                if m.case_type == case_type
                for t in m.get_subcase_types()}

    @memoized
    def grid_display_for_some_modules(self):
        return self.grid_menu_toggle_enabled() and self.grid_form_menus == 'some'

    @memoized
    def grid_display_for_all_modules(self):
        return self.grid_menu_toggle_enabled() and self.grid_form_menus == 'all'

    def grid_menu_toggle_enabled(self):
        return toggles.GRID_MENUS.enabled(self.domain)


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

    def create_profile(self, is_odk=False, langs=None):
        # we don't do odk for now anyway
        return remote_app.make_remote_profile(self, langs)

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

    def get_build_langs(self):
        if self.build_profiles:
            if len(self.build_profiles.keys()) > 1:
                raise AppEditingError('More than one app profile for a remote app')
            else:
                # return first profile, generated as part of lazy migration
                return self.build_profiles[self.build_profiles.keys()[0]].langs
        else:
            return self.langs

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

    def create_all_files(self, build_profile_id=None):
        langs_for_build = self.get_build_langs()
        files = {
            'profile.xml': self.create_profile(langs=langs_for_build),
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
                if tag == 'xform' and langs_for_build:
                    try:
                        xform = XForm(data)
                    except XFormException as e:
                        raise XFormException('In file %s: %s' % (location, e))
                    xform.exclude_languages(whitelist=langs_for_build)
                    data = xform.render()
                files.update({location: data})
        return files

    def make_questions_map(self):
        langs_for_build = self.get_build_langs()
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
                    questions = xform.get_questions(langs_for_build)
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


class LinkedApplication(Application):
    """
    An app that can pull changes from an app in a different domain.
    """
    # This is the id of the master application
    master = StringProperty()


def import_app(app_id_or_source, domain, source_properties=None, validate_source_domain=None):
    if isinstance(app_id_or_source, basestring):
        app_id = app_id_or_source
        source = get_app(None, app_id)
        src_dom = source['domain']
        if validate_source_domain:
            validate_source_domain(src_dom)
        source = source.export_json(dump_json=False)
    else:
        cls = get_correct_app_class(app_id_or_source)
        # Don't modify original app source
        app = cls.wrap(deepcopy(app_id_or_source))
        source = app.export_json(dump_json=False)
    try:
        attachments = source['_attachments']
    except KeyError:
        attachments = {}
    finally:
        source['_attachments'] = {}
    if source_properties is not None:
        for key, value in source_properties.iteritems():
            source[key] = value
    cls = get_correct_app_class(source)
    # Allow the wrapper to update to the current default build_spec
    if 'build_spec' in source:
        del source['build_spec']
    app = cls.from_source(source, domain)
    app.date_created = datetime.datetime.utcnow()
    app.cloudcare_enabled = domain_has_privilege(domain, privileges.CLOUDCARE)

    with app.atomic_blobs():
        for name, attachment in attachments.items():
            if re.match(ATTACHMENT_REGEX, name):
                app.put_attachment(attachment, name)

    if not app.is_remote_app():
        for _, m in app.get_media_objects():
            if domain not in m.valid_domains:
                m.valid_domains.append(domain)
                m.save()

    if not app.is_remote_app() and any(module.uses_usercase() for module in app.get_modules()):
        from corehq.apps.app_manager.util import enable_usercase
        enable_usercase(domain)

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
            name = trans(self.form.name, app.default_language, include_lang=False)
            module = app.get_module_by_unique_id(
                self.module_unique_id,
                error=_("Could not find form '{}'").format(name)
            )
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
            "by_domain_doc_type_date/view",
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
