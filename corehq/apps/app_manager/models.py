# coding=utf-8
from __future__ import absolute_import, unicode_literals

import calendar
import datetime
import hashlib
import itertools
import json
import logging
import os
import random
import re
import types
import uuid
from collections import defaultdict, namedtuple, Counter, OrderedDict
from functools import wraps

from copy import deepcopy
from distutils.version import LooseVersion
from functools import wraps
from io import BytesIO, open
from itertools import chain
from mimetypes import guess_type

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.db import models
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import SafeBytes
from django.utils.translation import override
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

import qrcode
import six
from couchdbkit import MultipleResultsFound, ResourceNotFound
from couchdbkit.exceptions import BadValueError
from jsonpath_rw import jsonpath, parse
from lxml import etree
from memoized import memoized
from six.moves import filter, map, range
from six.moves.urllib.parse import urljoin
from six.moves.urllib.request import urlopen

from corehq.apps.locations.models import SQLLocation
from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    DecimalProperty,
    DictProperty,
    Document,
    DocumentSchema,
    FloatProperty,
    IntegerProperty,
    ListProperty,
    SchemaDictProperty,
    SchemaListProperty,
    SchemaProperty,
    StringListProperty,
    StringProperty,
)
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.undo import DELETED_SUFFIX, DeleteRecord
from dimagi.utils.dates import DateSpan
from dimagi.utils.web import get_url_base, parse_int

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager import (
    app_strings,
    commcare_settings,
    current_builds,
    id_strings,
    remote_app,
)
from corehq.apps.app_manager.app_schemas.case_properties import (
    get_all_case_properties,
    get_usercase_properties,
)
from corehq.apps.app_manager.commcare_settings import check_condition
from corehq.apps.app_manager.const import *
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.dbaccessors import (
    domain_has_apps,
    get_app,
    get_latest_build_doc,
    get_latest_released_app_doc,
)
from corehq.apps.app_manager.util import (
    get_latest_app_release_by_location,
    expire_get_latest_app_release_by_location_cache,
)
from corehq.apps.app_manager.detail_screen import PropertyXpathGenerator
from corehq.apps.app_manager.exceptions import (
    AppEditingError,
    FormNotFoundException,
    IncompatibleFormTypeException,
    ModuleNotFoundException,
    RearrangeError,
    ScheduleError,
    VersioningError,
    XFormException,
    XFormIdNotUnique,
    XFormValidationError,
    XFormValidationFailed,
)
from corehq.apps.app_manager.feature_support import CommCareFeatureSupportMixin
from corehq.apps.app_manager.helpers.validators import (
    AdvancedFormValidator,
    AdvancedModuleValidator,
    ApplicationBaseValidator,
    ApplicationValidator,
    FormBaseValidator,
    FormValidator,
    IndexedFormBaseValidator,
    ModuleBaseValidator,
    ModuleValidator,
    ReportModuleValidator,
    ShadowFormValidator,
    ShadowModuleValidator,
)
from corehq.apps.app_manager.suite_xml import xml_models as suite_models
from corehq.apps.app_manager.suite_xml.generator import (
    MediaSuiteGenerator,
    SuiteGenerator,
)
from corehq.apps.app_manager.suite_xml.utils import get_select_chain
from corehq.apps.app_manager.tasks import prune_auto_generated_builds
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.app_manager.util import (
    LatestAppInfo,
    actions_use_usercase,
    get_and_assert_practice_user_in_domain,
    get_correct_app_class,
    get_latest_enabled_build_for_profile,
    get_latest_enabled_versions_per_profile,
    is_usercase_in_use,
    module_offers_search,
    save_xform,
    update_form_unique_ids,
    update_report_module_ids,
)
from corehq.apps.app_manager.xform import XForm
from corehq.apps.app_manager.xform import parse_xml as _parse_xml
from corehq.apps.app_manager.xform import validate_xform
from corehq.apps.app_manager.xpath import dot_interpolate, interpolate_xpath
from corehq.apps.appstore.models import SnapshotMixin
from corehq.apps.builds.models import (
    BuildRecord,
    BuildSpec,
    CommCareBuildConfig,
)
from corehq.apps.builds.utils import get_default_build_spec
from corehq.apps.domain.models import Domain, cached_property
from corehq.apps.hqmedia.models import (
    ApplicationMediaMixin,
    CommCareMultimedia,
    FormMediaMixin,
    ModuleMediaMixin,
)
from corehq.apps.integration.models import ApplicationIntegrationMixin
from corehq.apps.linked_domain.applications import (
    get_latest_master_app_release,
    get_master_app_version,
)
from corehq.apps.linked_domain.exceptions import ActionNotPermitted
from corehq.apps.reports.daterange import (
    get_daterange_start_end_dates,
    get_simple_dateranges,
)
from corehq.apps.translations.models import TranslationMixin
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError
from corehq.apps.userreports.util import get_static_report_mapping
from corehq.apps.users.dbaccessors.couch_users import (
    get_display_name_for_user_id,
)
from corehq.apps.users.util import cc_user_domain
from corehq.blobs.mixin import CODES, BlobMixin
from corehq.const import USER_DATE_FORMAT, USER_TIME_FORMAT
from corehq.util import bitly, view_utils
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.quickcache import quickcache
from corehq.util.soft_assert import soft_assert
from corehq.util.timer import TimingContext, time_method
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_domain

DETAIL_TYPES = ['case_short', 'case_long', 'ref_short', 'ref_long']

FIELD_SEPARATOR = ':'

ATTACHMENT_REGEX = r'[^/]*\.xml'

ANDROID_LOGO_PROPERTY_MAPPING = {
    'hq_logo_android_home': 'brand-banner-home',
    'hq_logo_android_login': 'brand-banner-login',
    'hq_logo_android_demo': 'brand-banner-home-demo',
}


LATEST_APK_VALUE = 'latest'
LATEST_APP_VALUE = 0

_soft_assert = soft_assert(to="{}@{}.com".format('npellegrino', 'dimagi'), exponential_backoff=True)


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


def app_template_dir(slug):
    return os.path.join(os.path.dirname(__file__), 'static', 'app_manager', 'template_apps', slug)


@memoized
def load_app_template(slug):
    with open(os.path.join(app_template_dir(slug), 'app.json')) as f:
        return json.load(f)


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
        return (
            other and isinstance(other, IndexedSchema)
            and (self.id == other.id)
            and (self._parent == other._parent)
        )

    def __ne__(self, other):
        return not self.__eq__(other)

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
            return types.MethodType(self, instance)


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


class OpenSubCaseAction(FormAction, IndexedSchema):

    case_type = StringProperty()
    case_name = StringProperty()
    reference_id = StringProperty()
    case_properties = DictProperty()
    repeat_context = StringProperty()
    # relationship = "child" for index to a parent case (default)
    # relationship = "extension" for index to a host case
    relationship = StringProperty(choices=['child', 'extension'], default='child')

    close_condition = SchemaProperty(FormActionCondition)

    @property
    def form_element_name(self):
        return 'subcase_{}'.format(self.id)


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

    get_subcases = IndexedSchema.Getter('subcases')

    def all_property_names(self):
        names = set()
        names.update(list(self.update_case.update.keys()))
        names.update(list(self.case_preload.preload.values()))
        for subcase in self.subcases:
            names.update(list(subcase.case_properties.keys()))
        return names

    def count_subcases_per_repeat_context(self):
        return Counter([action.repeat_context for action in self.subcases])


class CaseIndex(DocumentSchema):
    tag = StringProperty()
    reference_id = StringProperty(default='parent')
    relationship = StringProperty(choices=['child', 'extension', 'question'], default='child')
    # if relationship is 'question', this is the question path
    # question's response must be either "child" or "extension"
    relationship_question = StringProperty(default='')


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
    fixture_nodeset:     nodeset that returns the fixture options to display
    fixture_tag:         id of session datum where the result of user selection will be stored
    fixture_variable:    value from the fixture to store from the selection
    auto_select_fixture: boolean to autoselect the value if the nodeset only returns 1 result
    case_property:       case property to filter on
    arbitrary_datum_*:   adds an arbitrary datum with function before the action
    """
    fixture_nodeset = StringProperty()
    fixture_tag = StringProperty()
    fixture_variable = StringProperty()
    auto_select_fixture = BooleanProperty(default=False)
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
    load_case_from_fixture:   Configuration for loading a case using fixture data
    show_product_stock:       If True list the product stock using the module's Product List
                              configuration.
    product_program:          Only show products for this CommCare Supply program.
    case_index:               Used when a case should be created/updated as a child or extension case
                              of another case.
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
        names.update(list(self.preload.values()))
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

    def count_subcases_per_repeat_context(self):
        return Counter([action.repeat_context for action in self.get_open_subcase_actions()])


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
            app.lazy_put_attachment(old_contents.encode('utf-8'), filename)
            del form['contents']

        if not app.has_attachment(filename):
            source = ''
        else:
            source = app.lazy_fetch_attachment(filename)
            if isinstance(source, bytes):
                source = source.decode('utf-8')
            else:
                _soft_assert(False, type(source))

        return source

    def __set__(self, form, value):
        unique_id = form.get_unique_id()
        app = form.get_app()
        filename = "%s.xml" % unique_id
        if isinstance(value, six.text_type):
            value = value.encode('utf-8')
        else:
            _soft_assert(False, type(value))
        app.lazy_put_attachment(value, filename)
        form.clear_validation_cache()
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


class CustomAssertion(DocumentSchema):
    """Custom assertions to add to the assertions block
    test: The actual assertion to run
    locale_id: The id of the localizable string
    """
    test = StringProperty(required=True)
    text = DictProperty(StringProperty)


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


class CaseLoadReference(DocumentSchema):
    """
    This is the schema for a load reference that is used in validation and expected
    to be worked with when using `CaseReferences`. The format is different from the
    dict of:

    {
      'path': ['list', 'of', 'properties']
    }

    That is stored on the model and expected in Vellum, but as we add more information
    (like case types) to the load model this format will be easier to extend.
    """
    _allow_dynamic_properties = False
    path = StringProperty()
    properties = ListProperty(six.text_type)


class CaseSaveReference(DocumentSchema):
    """
    This is the schema for what Vellum writes to HQ and what is expected to be stored on the
    model (reference by a dict where the keys are paths).
    """
    _allow_dynamic_properties = False
    case_type = StringProperty()
    properties = ListProperty(six.text_type)
    create = BooleanProperty(default=False)
    close = BooleanProperty(default=False)


class CaseSaveReferenceWithPath(CaseSaveReference):
    """
    Like CaseLoadReference, this is the model that is expected to be worked with as it
    contains the complete information about the reference in a single place.
    """
    path = StringProperty()


class CaseReferences(DocumentSchema):
    """
    The case references associated with a form. This is dependent on Vellum's API that sends
    case references to HQ.

    load: is a dict of question paths to lists of properties (see `CaseLoadReference`),
    save: is a dict of question paths to `CaseSaveReference` objects.

    The intention is that all usage of the objects goes through the `get_load_references` and
    `get_save_references` helper functions.
    """
    _allow_dynamic_properties = False
    load = DictProperty()
    save = SchemaDictProperty(CaseSaveReference)

    def validate(self, required=True):
        super(CaseReferences, self).validate()
        # call this method to force validation to run on the other referenced types
        # since load is not a defined schema (yet)
        list(self.get_load_references())

    def get_load_references(self):
        """
        Returns a generator of `CaseLoadReference` objects containing all the load references.
        """
        for path, properties in self.load.items():
            yield CaseLoadReference(path=path, properties=list(properties))

    def get_save_references(self):
        """
        Returns a generator of `CaseSaveReferenceWithPath` objects containing all the save references.
        """
        for path, reference in self.save.items():
            ref_copy = reference.to_json()
            ref_copy['path'] = path
            yield CaseSaveReferenceWithPath.wrap(ref_copy)


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
            return 'h{hash}'.format(hash=hashlib.md5(self.key.encode('UTF-8')).hexdigest()[:8])
        else:
            return 'k{key}'.format(key=self.key)

    def key_as_condition(self, property=None):
        if self.treat_as_expression:
            condition = dot_interpolate(self.key, property) if property else self.key
            return "{condition}".format(condition=condition)
        else:
            return "{property} = '{key}'".format(
                property=property,
                key=self.key
            )

    def ref_to_key_variable(self, index, sort_or_display):
        if sort_or_display == "sort":
            key_as_var = "{}, ".format(index)
        elif sort_or_display == "display":
            key_as_var = "${var_name}, ".format(var_name=self.key_as_variable)

        return key_as_var


class FormBase(DocumentSchema):
    """
    Part of a Managed Application; configuration for a form.
    Translates to a second-level menu on the phone

    """
    form_type = None

    name = DictProperty(six.text_type)
    name_enum = SchemaListProperty(MappingItem)
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
    post_form_workflow_fallback = StringProperty(
        choices=WORKFLOW_FALLBACK_OPTIONS,
        default=None,
    )
    auto_gps_capture = BooleanProperty(default=False)
    no_vellum = BooleanProperty(default=False)
    form_links = SchemaListProperty(FormLink)
    schedule_form_id = StringProperty()
    custom_assertions = SchemaListProperty(CustomAssertion)
    custom_instances = SchemaListProperty(CustomInstance)
    case_references_data = SchemaProperty(CaseReferences)
    is_release_notes_form = BooleanProperty(default=False)
    enable_release_notes = BooleanProperty(default=False)

    @classmethod
    def wrap(cls, data):
        data.pop('validation_cache', '')

        if cls is FormBase:
            doc_type = data['doc_type']
            if doc_type == 'Form':
                return Form.wrap(data)
            elif doc_type == 'AdvancedForm':
                return AdvancedForm.wrap(data)
            elif doc_type == 'ShadowForm':
                return ShadowForm.wrap(data)
            else:
                raise ValueError('Unexpected doc_type for Form', doc_type)
        else:
            return super(FormBase, cls).wrap(data)

    @property
    def case_references(self):
        return self.case_references_data or CaseReferences()

    def requires_case(self):
        return False

    def get_action_type(self):
        return ''

    def get_validation_cache(self):
        return self.validation_cache

    def set_validation_cache(self, cache):
        self.validation_cache = cache

    def clear_validation_cache(self):
        self.set_validation_cache(None)

    @property
    def validator(self):
        return FormBaseValidator(self)

    def is_allowed_to_be_release_notes_form(self):
        # checks if this form can be marked as a release_notes form
        #   based on whether it belongs to a training_module
        #   and if no other form is already marked as release_notes form
        module = self.get_module()
        if not module or not module.is_training_module:
            return False

        forms = module.get_forms()
        for form in forms:
            if form.is_release_notes_form and form.unique_id != self.unique_id:
                return False
        return True

    @property
    def uses_cases(self):
        return (
            self.requires_case()
            or self.get_action_type() != 'none'
            or self.form_type == 'advanced_form'
        )

    @case_references.setter
    def case_references(self, case_references):
        self.case_references_data = case_references

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
        vc = self.get_validation_cache()
        if vc is None:
            # todo: now that we don't use formtranslate, does this still apply?
            # formtranslate requires all attributes to be valid xpaths, but
            # vellum namespaced attributes aren't
            form = self.wrapped_xform()
            form.strip_vellum_ns_attributes()
            try:
                if form.xml is not None:
                    validate_xform(self.get_app().domain, etree.tostring(form.xml, encoding="unicode"))
            except XFormValidationError as e:
                validation_dict = {
                    "fatal_error": e.fatal_error,
                    "validation_problems": e.validation_problems,
                    "version": e.version,
                }
                vc = json.dumps(validation_dict)
            else:
                vc = ""
            self.set_validation_cache(vc)
        if vc:
            try:
                raise XFormValidationError(**json.loads(vc))
            except ValueError:
                self.clear_validation_cache()
                return self.validate_form()
        return self

    def is_a_disabled_release_form(self):
        return self.is_release_notes_form and not self.enable_release_notes

    @property
    def timing_context(self):
        return self.get_app().timing_context

    def validate_for_build(self, validate_module=True):
        return self.validator.validate_for_build(validate_module)

    def get_unique_id(self):
        """
        Return unique_id if it exists, otherwise initialize it

        Does _not_ force a save, so it's the caller's responsibility to save the app

        """
        if not self.unique_id:
            self.unique_id = uuid.uuid4().hex
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
        xform.add_missing_instances(app.domain)

    def render_xform(self, build_profile_id=None):
        xform = XForm(self.source)
        self.add_stuff_to_xform(xform, build_profile_id)
        return xform.render()

    def cached_get_questions(self):
        """
        Call to get_questions with a superset of necessary information, so
        it can hit the same cache across common app-building workflows
        """
        # it is important that this is called with the same params every time
        return self.get_questions([], include_triggers=True, include_groups=True)

    @time_method()
    @quickcache(['self.source', 'langs', 'include_triggers', 'include_groups', 'include_translations'],
                timeout=24 * 60 * 60)
    def get_questions(self, langs, include_triggers=False,
                      include_groups=False, include_translations=False):
        try:
            return XForm(self.source).get_questions(
                langs=langs,
                include_triggers=include_triggers,
                include_groups=include_groups,
                include_translations=include_translations,
            )
        except XFormException as e:
            raise XFormException(_('Error in form "{}": {}')
                                 .format(trans(self.name), six.text_type(e)))

    @memoized
    def get_case_property_name_formatter(self):
        """Get a function that formats case property names

        The returned function requires two arguments
        `(case_property_name, data_path)` and returns a string.
        """
        valid_paths = {}
        if toggles.MM_CASE_PROPERTIES.enabled(self.get_app().domain):
            try:
                valid_paths = {question['value']: question['tag']
                               for question in self.get_questions(langs=[])}
            except XFormException:
                # punt on invalid xml (sorry, no rich attachments)
                valid_paths = {}

        def format_key(key, path):
            if valid_paths.get(path) == "upload":
                return "{}{}".format(ATTACHMENT_PREFIX, key)
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
            self.source = source.render().decode('utf-8')

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

    def get_save_to_case_updates(self):
        """
        Get a flat list of case property names from save to case questions
        """
        updates_by_case_type = defaultdict(set)
        for save_to_case_update in self.case_references_data.get_save_references():
            case_type = save_to_case_update.case_type
            updates_by_case_type[case_type].update(save_to_case_update.properties)
        return updates_by_case_type


class IndexedFormBase(FormBase, IndexedSchema, CommentMixin):

    def get_app(self):
        return self._parent._parent

    def get_module(self):
        return self._parent

    def get_case_type(self):
        return self._parent.case_type

    @property
    def validator(self):
        return IndexedFormBaseValidator(self)

    def get_all_case_updates(self):
        """
        Collate contributed case updates from all sources within the form

        Subclass must have helper methods defined:

        - get_case_updates
        - get_all_contributed_subcase_properties
        - get_save_to_case_updates

        :return: collated {<case_type>: set([<property>])}

        """
        updates_by_case_type = defaultdict(set)

        for case_type, updates in self.get_case_updates().items():
            updates_by_case_type[case_type].update(updates)

        for case_type, updates in self.get_all_contributed_subcase_properties().items():
            updates_by_case_type[case_type].update(updates)

        for case_type, updates in self.get_save_to_case_updates().items():
            updates_by_case_type[case_type].update(updates)

        return updates_by_case_type

    def get_case_updates_for_case_type(self, case_type):
        """
        Like get_case_updates filtered by a single case type

        subclass must implement `get_case_updates`

        """
        return self.get_case_updates().get(case_type, [])


class JRResourceProperty(StringProperty):

    def validate(self, value, required=True):
        super(JRResourceProperty, self).validate(value, required)
        if value is not None and not value.startswith('jr://'):
            raise BadValueError("JR Resources must start with 'jr://': {!r}".format(value))
        return value


class CustomIcon(DocumentSchema):
    """
    A custom icon to display next to a module or a form.
    The property "form" identifies what kind of icon this would be, for ex: badge
    One can set either a simple text to display or
    an xpath expression to be evaluated for example count of cases within.
    """
    form = StringProperty()
    text = DictProperty(six.text_type)
    xpath = StringProperty()


class NavMenuItemMediaMixin(DocumentSchema):
    """
        Language-specific icon and audio.
        Properties are map of lang-code to filepath
    """

    # These were originally DictProperty(JRResourceProperty),
    # but jsonobject<0.9.0 didn't properly support passing in a property to a container type
    # so it was actually wrapping as a StringPropery
    # too late to retroactively apply that validation,
    # so now these are DictProperty(StringProperty)
    media_image = DictProperty(StringProperty)
    media_audio = DictProperty(StringProperty)
    custom_icons = ListProperty(CustomIcon)

    # When set to true, all languages use the specific media from the default language
    use_default_image_for_all = BooleanProperty(default=False)
    use_default_audio_for_all = BooleanProperty(default=False)

    @classmethod
    def wrap(cls, data):
        # Lazy migration from single-language media to localizable media
        for media_attr in ('media_image', 'media_audio'):
            old_media = data.get(media_attr, None)
            if old_media:
                # Single-language media was stored in a plain string.
                # Convert this to a dict, using a dummy key because we
                # don't know the app's supported or default lang yet.
                if isinstance(old_media, six.string_types):
                    soft_assert_type_text(old_media)
                    new_media = {'default': old_media}
                    data[media_attr] = new_media
                elif isinstance(old_media, dict):
                    # Once the media has localized data, discard the dummy key
                    if 'default' in old_media and len(old_media) > 1:
                        old_media.pop('default')

        return super(NavMenuItemMediaMixin, cls).wrap(data)

    def get_app(self):
        raise NotImplementedError

    def _get_media_by_language(self, media_attr, lang, strict=False, build_profile_id=None):
        """
        Return media-path for given language if one exists, else 1st path in the
        sorted lang->media-path list

        *args:
            media_attr: one of 'media_image' or 'media_audio'
            lang: language code
        **kwargs:
            strict: whether to return None if media-path is not set for lang or
                to return first path in sorted lang->media-path list
            build_profile_id: If this is provided and strict is False, only return
                media in one of the profile's languages
        """
        assert media_attr in ('media_image', 'media_audio')
        app = self.get_app()

        if ((self.use_default_image_for_all and media_attr == 'media_image')
                or (self.use_default_audio_for_all and media_attr == 'media_audio')):
            lang = app.default_language

        media_dict = getattr(self, media_attr)
        if not media_dict:
            return None
        if media_dict.get(lang, ''):
            return media_dict[lang]
        if not strict:
            # if the queried lang key doesn't exist,
            # return the first in the sorted list
            for lang, item in sorted(media_dict.items()):
                if not build_profile_id or lang in app.build_profiles[build_profile_id].langs:
                    return item

    @property
    def default_media_image(self):
        # For older apps that were migrated: just return the first available item
        self._assert_unexpected_default_media_call('media_image')
        return self.icon_by_language('')

    @property
    def default_media_audio(self):
        # For older apps that were migrated: just return the first available item
        self._assert_unexpected_default_media_call('media_audio')
        return self.audio_by_language('')

    def _assert_unexpected_default_media_call(self, media_attr):
        assert media_attr in ('media_image', 'media_audio')
        media = getattr(self, media_attr)
        if isinstance(media, dict) and list(media) == ['default']:
            from corehq.util.view_utils import get_request
            request = get_request()
            url = ''
            if request:
                url = request.META.get('HTTP_REFERER')
            _assert = soft_assert(['jschweers' + '@' + 'dimagi.com'])
            _assert(False, 'Called default_media_image on app with localized media: {}'.format(url))

    def icon_by_language(self, lang, strict=False, build_profile_id=None):
        return self._get_media_by_language('media_image', lang, strict=strict, build_profile_id=build_profile_id)

    def audio_by_language(self, lang, strict=False, build_profile_id=None):
        return self._get_media_by_language('media_audio', lang, strict=strict, build_profile_id=build_profile_id)

    def custom_icon_form_and_text_by_language(self, lang):
        custom_icon = self.custom_icon
        if custom_icon:
            custom_icon_text = custom_icon.text.get(lang, custom_icon.text.get(self.get_app().default_language))
            return custom_icon.form, custom_icon_text
        return None, None

    def _set_media(self, media_attr, lang, media_path):
        """
            Caller's responsibility to save doc.
            Currently only called from the view which saves after all Edits
        """
        assert media_attr in ('media_image', 'media_audio')

        media_dict = getattr(self, media_attr) or {}
        old_value = media_dict.get(lang)
        media_dict[lang] = media_path or ''
        setattr(self, media_attr, media_dict)
        # remove the entry from app multimedia mappings if media is being removed now
        # This does not remove the multimedia but just it's reference in mapping
        # Added it here to ensure it's always set instead of getting it only when needed
        app = self.get_app()
        if old_value and not media_path:
            # expire all_media_paths before checking for media path used in Application
            app.all_media.reset_cache(app)
            app.all_media_paths.reset_cache(app)
            if old_value not in app.all_media_paths():
                app.multimedia_map.pop(old_value, None)

    def set_icon(self, lang, icon_path):
        self._set_media('media_image', lang, icon_path)

    def set_audio(self, lang, audio_path):
        self._set_media('media_audio', lang, audio_path)

    def _all_media_paths(self, media_attr, lang=None):
        assert media_attr in ('media_image', 'media_audio')
        media_dict = getattr(self, media_attr) or {}
        valid_media_paths = set()
        for key, value in media_dict.items():
            if value and (lang is None or key == lang):
                valid_media_paths.add(value)
        return valid_media_paths

    def uses_image(self, build_profile_id=None):
        app = self.get_app()
        langs = app.build_profiles[build_profile_id].langs if build_profile_id else app.langs
        return any([self.icon_app_string(lang) for lang in langs])

    def uses_audio(self, build_profile_id=None):
        app = self.get_app()
        langs = app.build_profiles[build_profile_id].langs if build_profile_id else app.langs
        return any([self.audio_app_string(lang) for lang in langs])

    def all_image_paths(self, lang=None):
        return self._all_media_paths('media_image', lang=lang)

    def all_audio_paths(self, lang=None):
        return self._all_media_paths('media_audio', lang=lang)

    def icon_app_string(self, lang, for_default=False, build_profile_id=None):
        """
        Return lang/app_strings.txt translation for given lang
        if a path exists for the lang

        **kwargs:
            for_default: whether app_string is for default/app_strings.txt
        """

        if not for_default and self.icon_by_language(lang, strict=True):
            return self.icon_by_language(lang, strict=True)

        if for_default:
            return self.icon_by_language(lang, strict=False, build_profile_id=build_profile_id)

    def audio_app_string(self, lang, for_default=False, build_profile_id=None):
        """
            see note on self.icon_app_string
        """

        if not for_default and self.audio_by_language(lang, strict=True):
            return self.audio_by_language(lang, strict=True)

        if for_default:
            return self.audio_by_language(lang, strict=False, build_profile_id=build_profile_id)

    @property
    def custom_icon(self):
        if self.custom_icons:
            return self.custom_icons[0]


class Form(IndexedFormBase, FormMediaMixin, NavMenuItemMediaMixin):
    form_type = 'module_form'

    form_filter = StringProperty()
    requires = StringProperty(choices=["case", "referral", "none"], default="none")
    actions = SchemaProperty(FormActions)

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
            getter = 'get_{}'.format(action_type)
            if hasattr(self.actions, getter):
                # user getter if there is one
                a = list(getattr(self.actions, getter)())
            else:
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

    @property
    def validator(self):
        return FormValidator(self)

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

    def get_case_updates(self):
        # This method is used by both get_all_case_properties and
        # get_usercase_properties. In the case of usercase properties, use
        # the usercase_update action, and for normal cases, use the
        # update_case action
        case_type = self.get_module().case_type
        format_key = self.get_case_property_name_formatter()

        return {
            case_type: {
                format_key(*item) for item in self.actions.update_case.update.items()},
            USERCASE_TYPE: {
                format_key(*item) for item in self.actions.usercase_update.update.items()}
        }

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
        refs = self.case_references_data or CaseReferences()
        if not refs.load and self.actions.load_from_form.preload:
            # for backward compatibility
            # preload only has one reference per question path
            preload = self.actions.load_from_form.preload
            refs.load = {key: [value] for key, value in six.iteritems(preload)}
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
    def get_all_contributed_subcase_properties(self):
        case_properties = defaultdict(set)
        for subcase in self.actions.subcases:
            case_properties[subcase.case_type].update(list(subcase.case_properties.keys()))
        return case_properties

    @memoized
    def get_contributed_case_relationships(self):
        case_relationships_by_child_type = defaultdict(set)
        parent_case_type = self.get_module().case_type
        for subcase in self.actions.subcases:
            child_case_type = subcase.case_type
            if child_case_type != parent_case_type and (
                    self.actions.open_case.is_active() or
                    self.actions.update_case.is_active() or
                    self.actions.close_case.is_active()):
                case_relationships_by_child_type[child_case_type].add(
                    (parent_case_type, subcase.reference_id or 'parent'))
        return case_relationships_by_child_type


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
    relevant = StringProperty()


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
    useXpathExpression = BooleanProperty(default=False)
    format = StringProperty()

    enum = SchemaListProperty(MappingItem)
    graph_configuration = SchemaProperty(GraphConfiguration)
    case_tile_field = StringProperty()

    late_flag = IntegerProperty(default=30)
    advanced = StringProperty(default="")
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
            data['enum'] = sorted(
                [{'key': key, 'value': value} for key, value in data['enum'].items()],
                key=lambda d: d['key'],
            )

        # Lazy migration: xpath expressions from format to first-class property
        if data.get('format') == 'calculate':
            property_xpath = PropertyXpathGenerator(None, None, None, super(DetailColumn, cls).wrap(data)).xpath
            data['field'] = dot_interpolate(data.get('calc_xpath', '.'), property_xpath)
            data['useXpathExpression'] = True
            data['hasAutocomplete'] = False
            data['format'] = 'plain'

        return super(DetailColumn, cls).wrap(data)

    @classmethod
    def from_json(cls, data):
        from corehq.apps.app_manager.views.media_utils import interpolate_media_path

        to_ret = cls.wrap(data)
        if to_ret.format == 'enum-image':
            # interpolate icons-paths
            for item in to_ret.enum:
                for lang, path in six.iteritems(item.value):
                    item.value[lang] = interpolate_media_path(path)
        return to_ret

    @property
    def invisible(self):
        return self.format == 'invisible'


class SortElement(IndexedSchema):
    field = StringProperty()
    type = StringProperty()
    direction = StringProperty()
    blanks = StringProperty()
    display = DictProperty()
    sort_calculation = StringProperty(default="")

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
    sort_nodeset_columns = BooleanProperty()
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
    # use case tile context persisted over forms from another module
    persistent_case_tile_from_module = StringProperty()
    # If True, the in form tile can be pulled down to reveal all the case details.
    pull_down_tile = BooleanProperty()

    print_template = DictProperty()

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

    def sort_nodeset_columns_for_detail(self):
        return (
            self.display == "long" and
            self.sort_nodeset_columns and
            any(tab for tab in self.get_tabs() if tab.has_nodeset)
        )


class CaseList(IndexedSchema, NavMenuItemMediaMixin):

    label = DictProperty()
    show = BooleanProperty(default=False)

    def rename_lang(self, old_lang, new_lang):
        _rename_key(self.label, old_lang, new_lang)

    def get_app(self):
        return self._module.get_app()


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
    search_button_display_condition = StringProperty()
    include_closed = BooleanProperty(default=False)
    default_properties = SchemaListProperty(DefaultCaseSearchProperty)
    blacklisted_owner_ids_expression = StringProperty()


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
    post_form_workflow = StringProperty(
        default=WORKFLOW_DEFAULT,
        choices=REGISTRATION_FORM_WORFLOWS,
    )

    def rename_lang(self, old_lang, new_lang):
        _rename_key(self.label, old_lang, new_lang)

    def get_app(self):
        return self._module.get_app()


class ModuleBase(IndexedSchema, ModuleMediaMixin, NavMenuItemMediaMixin, CommentMixin):
    name = DictProperty(six.text_type)
    name_enum = SchemaListProperty(MappingItem)
    unique_id = StringProperty()
    case_type = StringProperty()
    case_list_form = SchemaProperty(CaseListForm)
    module_filter = StringProperty()
    put_in_root = BooleanProperty(default=False)
    root_module_id = StringProperty()
    fixture_select = SchemaProperty(FixtureSelect)
    auto_select_case = BooleanProperty(default=False)
    is_training_module = BooleanProperty(default=False)

    def __init__(self, *args, **kwargs):
        super(ModuleBase, self).__init__(*args, **kwargs)
        self.assign_references()

    @property
    def is_surveys(self):
        return self.case_type == ""

    def assign_references(self):
        if hasattr(self, 'case_list'):
            self.case_list._module = self
        if hasattr(self, 'case_list_form'):
            self.case_list_form._module = self

    @classmethod
    def wrap(cls, data):
        if cls is ModuleBase:
            doc_type = data['doc_type']
            if doc_type == 'Module':
                return Module.wrap(data)
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
            self.unique_id = uuid.uuid4().hex
        return self.unique_id

    get_forms = IndexedSchema.Getter('forms')

    def get_suite_forms(self):
        return [f for f in self.get_forms() if not f.is_a_disabled_release_form()]

    @parse_int([1])
    def get_form(self, i):

        try:
            return self.forms[i].with_id(i % len(self.forms), self)
        except IndexError:
            raise FormNotFoundException()

    def get_form_index(self, unique_id):
        for index, form in enumerate(self.get_forms()):
            if form.unique_id == unique_id:
                return index
        error = _("Could not find form with ID='{unique_id}' in module '{module_name}'.").format(
            module_name=self.name, unique_id=unique_id)
        raise FormNotFoundException(error)

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

    def root_requires_same_case(self):
        return self.root_module \
            and self.root_module.case_type == self.case_type \
            and self.root_module.all_forms_require_a_case()

    def get_case_types(self):
        return set([self.case_type])

    def get_app(self):
        return self._parent

    def default_name(self, app=None):
        if not app:
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

    def get_form_by_unique_id(self, unique_id):
        for form in self.get_forms():
            if form.get_unique_id() == unique_id:
                return form

    @property
    def validator(self):
        return ModuleBaseValidator(self)

    def validate_for_build(self):
        return self.validator.validate_for_build()

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


class ModuleDetailsMixin(object):

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

    @property
    def search_detail(self):
        return deepcopy(self.case_details.short)

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
        details = [
            ('case_short', self.case_details.short, True),
            ('case_long', self.case_details.long, True),
            ('ref_short', self.ref_details.short, False),
            ('ref_long', self.ref_details.long, False),
        ]
        if module_offers_search(self) and not self.case_details.short.custom_xml:
            details.append(('search_short', self.search_detail, True))
        return tuple(details)


class Module(ModuleBase, ModuleDetailsMixin):
    """
    A group of related forms, and configuration that applies to them all.
    Translates to a top-level menu on the phone.

    """
    module_type = 'basic'
    forms = SchemaListProperty(Form)
    case_details = SchemaProperty(DetailPair)
    ref_details = SchemaProperty(DetailPair)
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
                header={(lang or 'en'): _("Name")},
                field='name',
                model='case',
                hasAutocomplete=True,
            )]
        )
        module = cls(
            name={(lang or 'en'): name or _("Untitled Module")},
            forms=[],
            case_type='',
            case_details=DetailPair(
                short=Detail(detail.to_json()),
                long=Detail(detail.to_json()),
            ),
        )
        module.get_or_create_unique_id()
        return module

    @classmethod
    def new_training_module(cls, name, lang):
        module = cls.new_module(name, lang)
        module.is_training_module = True
        return module

    def new_form(self, name, lang, attachment=Ellipsis):
        from corehq.apps.app_manager.views.utils import get_blank_form_xml
        lang = lang if lang else "en"
        name = name if name else _("Untitled Form")
        form = Form(
            name={lang: name},
        )
        self.forms.append(form)
        form = self.get_form(-1)
        if attachment == Ellipsis:
            attachment = get_blank_form_xml(name)
        form.source = attachment
        return form

    def add_insert_form(self, from_module, form, index=None, with_source=False):
        if isinstance(form, Form):
            new_form = form
        elif isinstance(form, AdvancedForm) and not len(list(form.actions.get_all_actions())):
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
            raise IncompatibleFormTypeException(_('''
                Cannot move an advanced form with actions into a basic menu.
            '''))

        if index is not None:
            self.forms.insert(index, new_form)
        else:
            self.forms.append(new_form)
        return self.get_form(index or -1)

    @property
    def validator(self):
        return ModuleValidator(self)

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


class AdvancedForm(IndexedFormBase, FormMediaMixin, NavMenuItemMediaMixin):
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
            if preload and list(preload.values())[0].startswith('/'):
                action['preload'] = {v: k for k, v in preload.items()}

        return super(AdvancedForm, cls).wrap(data)

    def pre_delete_hook(self):
        try:
            self.disable_schedule()
        except (ScheduleError, TypeError, AttributeError) as e:
            logging.error("There was a {error} while running the pre_delete_hook on {form_id}. "
                          "There is probably nothing to worry about, but you could check to make sure "
                          "that there are no issues with this form.".format(error=e, form_id=self.unique_id))

    def get_action_type(self):
        actions = self.actions.actions_meta_by_tag
        by_type = defaultdict(list)
        action_type = []
        for action_tag, action_meta in six.iteritems(actions):
            by_type[action_meta.get('type')].append(action_tag)

        for type, tag_list in six.iteritems(by_type):
            action_type.append('{} ({})'.format(type, ', '.join(filter(None, tag_list))))

        return ' '.join(action_type)

    def pre_move_hook(self, from_module, to_module):
        if from_module != to_module:
            try:
                self.disable_schedule()
            except (ScheduleError, TypeError, AttributeError) as e:
                logging.error("There was a {error} while running the pre_move_hook on {form_id}. "
                              "There is probably nothing to worry about, but you could check to make sure "
                              "that there are no issues with this module.".format(error=e, form_id=self.unique_id))

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

    @property
    def validator(self):
        return AdvancedFormValidator(self)

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
        if self.schedule:
            self.schedule.enabled = False
        phase = self.get_phase()
        if phase:
            phase.remove_form(self)

    def get_case_updates(self):
        updates_by_case_type = defaultdict(set)
        format_key = self.get_case_property_name_formatter()
        for action in self.actions.get_all_actions():
            case_type = action.case_type
            updates_by_case_type[case_type].update(
                format_key(*item) for item in six.iteritems(action.case_properties))
        if self.schedule and self.schedule.enabled and self.source:
            xform = self.wrapped_xform()
            self.add_stuff_to_xform(xform)
            scheduler_updates = xform.get_scheduler_case_updates()
        else:
            scheduler_updates = {}

        for case_type, updates in scheduler_updates.items():
            updates_by_case_type[case_type].update(updates)

        return updates_by_case_type

    @memoized
    def get_all_contributed_subcase_properties(self):
        case_properties = defaultdict(set)
        for subcase in self.actions.get_subcase_actions():
            case_properties[subcase.case_type].update(list(subcase.case_properties.keys()))
        return case_properties

    @memoized
    def get_contributed_case_relationships(self):
        case_relationships_by_child_type = defaultdict(set)
        for subcase in self.actions.get_subcase_actions():
            child_case_type = subcase.case_type
            for case_index in subcase.case_indices:
                parent = self.actions.get_action_from_tag(case_index.tag)
                if parent:
                    case_relationships_by_child_type[child_case_type].add(
                        (parent.case_type, case_index.reference_id or 'parent'))
        return case_relationships_by_child_type


class ShadowForm(AdvancedForm):
    form_type = 'shadow_form'
    # The unqiue id of the form we are shadowing
    shadow_parent_form_id = FormIdProperty("modules[*].forms[*].shadow_parent_form_id")

    # form actions to be merged with the parent actions
    extra_actions = SchemaProperty(AdvancedFormActions)

    def __init__(self, *args, **kwargs):
        super(ShadowForm, self).__init__(*args, **kwargs)
        self._shadow_parent_form = None

    @property
    def shadow_parent_form(self):
        if not self.shadow_parent_form_id:
            return None
        else:
            if not self._shadow_parent_form or self._shadow_parent_form.unique_id != self.shadow_parent_form_id:
                app = self.get_app()
                try:
                    self._shadow_parent_form = app.get_form(self.shadow_parent_form_id)
                except FormNotFoundException:
                    self._shadow_parent_form = None
            return self._shadow_parent_form

    @property
    def source(self):
        if self.shadow_parent_form:
            return self.shadow_parent_form.source
        from corehq.apps.app_manager.views.utils import get_blank_form_xml
        return get_blank_form_xml("")

    def get_validation_cache(self):
        if not self.shadow_parent_form:
            return None
        return self.shadow_parent_form.validation_cache

    def set_validation_cache(self, cache):
        if self.shadow_parent_form:
            self.shadow_parent_form.validation_cache = cache

    @property
    def xmlns(self):
        if not self.shadow_parent_form:
            return None
        else:
            return self.shadow_parent_form.xmlns

    @property
    def actions(self):
        if not self.shadow_parent_form:
            shadow_parent_actions = AdvancedFormActions()
        else:
            shadow_parent_actions = self.shadow_parent_form.actions
        return self._merge_actions(shadow_parent_actions, self.extra_actions)

    @property
    def validator(self):
        return ShadowFormValidator(self)

    def get_shadow_parent_options(self):
        options = [
            (form.get_unique_id(), '{} / {}'.format(form.get_module().default_name(), form.default_name()))
            for form in self.get_app().get_forms() if form.form_type == "advanced_form"
        ]
        if self.shadow_parent_form_id and self.shadow_parent_form_id not in [x[0] for x in options]:
            options = [(self.shadow_parent_form_id, ugettext_lazy("Unknown, please change"))] + options
        return options

    @staticmethod
    def _merge_actions(source_actions, extra_actions):

        new_actions = []
        source_action_map = {
            action.case_tag: action
            for action in source_actions.load_update_cases
        }
        overwrite_properties = [
            "case_type",
            "details_module",
            "auto_select",
            "load_case_from_fixture",
            "show_product_stock",
            "product_program",
            "case_index",
        ]

        for action in extra_actions.load_update_cases:
            if action.case_tag in source_action_map:
                new_action = LoadUpdateAction.wrap(source_action_map[action.case_tag].to_json())
            else:
                new_action = LoadUpdateAction(case_tag=action.case_tag)

            for prop in overwrite_properties:
                setattr(new_action, prop, getattr(action, prop))
            new_actions.append(new_action)

        return AdvancedFormActions(
            load_update_cases=new_actions,
            open_cases=source_actions.open_cases,  # Shadow form is not allowed to specify any open case actions
        )


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
    forms = SchemaListProperty(FormBase)
    case_details = SchemaProperty(DetailPair)
    product_details = SchemaProperty(DetailPair)
    case_list = SchemaProperty(CaseList)
    has_schedule = BooleanProperty()
    schedule_phases = SchemaListProperty(SchedulePhase)
    get_schedule_phases = IndexedSchema.Getter('schedule_phases')
    search_config = SchemaProperty(CaseSearch)

    @property
    def is_surveys(self):
        return False

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
                header={(lang or 'en'): _("Name")},
                field='name',
                model='case',
            )]
        )

        module = AdvancedModule(
            name={(lang or 'en'): name or _("Untitled Module")},
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
                            header={(lang or 'en'): _("Product")},
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

    def new_form(self, name, lang, attachment=Ellipsis):
        from corehq.apps.app_manager.views.utils import get_blank_form_xml
        lang = lang if lang else "en"
        name = name if name else _("Untitled Form")
        form = AdvancedForm(
            name={lang: name},
        )
        form.schedule = FormSchedule(enabled=False)

        self.forms.append(form)
        form = self.get_form(-1)
        if attachment == Ellipsis:
            attachment = get_blank_form_xml(name)
        form.source = attachment
        return form

    def new_shadow_form(self, name, lang):
        lang = lang if lang else "en"
        name = name if name else _("Untitled Form")
        form = ShadowForm(
            name={lang: name},
            no_vellum=True,
        )
        form.schedule = FormSchedule(enabled=False)

        self.forms.append(form)
        form = self.get_form(-1)
        form.get_unique_id()  # This function sets the unique_id. Normally setting the source sets the id.
        return form

    def add_insert_form(self, from_module, form, index=None, with_source=False):
        if isinstance(form, AdvancedForm):
            new_form = form
        elif isinstance(form, Form):
            new_form = AdvancedForm(
                name=form.name,
                form_filter=form.form_filter,
                media_image=form.media_image,
                media_audio=form.media_audio,
                comment=form.comment,
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
                    from_app = from_module.get_app()  # A form can be copied from a module in a different app.
                    select_chain = get_select_chain(from_app, from_module, include_self=False)
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

        for form in self.get_forms():
            if any(action.case_type == self.case_type for action in form.actions.load_update_cases):
                return True

    def all_forms_require_a_case(self):
        return all(form.requires_case() for form in self.forms)

    @property
    def search_detail(self):
        return deepcopy(self.case_details.short)

    def get_details(self):
        details = [
            ('case_short', self.case_details.short, True),
            ('case_long', self.case_details.long, True),
            ('product_short', self.product_details.short, self.get_app().commtrack_enabled),
            ('product_long', self.product_details.long, False),
        ]
        if module_offers_search(self) and not self.case_details.short.custom_xml:
            details.append(('search_short', self.search_detail, True))
        return details

    @property
    def validator(self):
        return AdvancedModuleValidator(self)

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

        deleted_phases_with_forms = [anchor for anchor, phase in six.iteritems(old_phases) if len(phase.forms)]
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
    return ui_filter.value(**{ui_filter.name: user.location_id,
                              'request_user': user})


def _filter_by_location_ids(user, ui_filter):
    from corehq.apps.userreports.reports.filters.values import CHOICE_DELIMITER
    return ui_filter.value(**{ui_filter.name: CHOICE_DELIMITER.join(user.assigned_location_ids),
                              'request_user': user})


def _filter_by_username(user, ui_filter):
    from corehq.apps.reports_core.filters import Choice
    return Choice(value=user.raw_username, display=None)


def _filter_by_user_id(user, ui_filter):
    from corehq.apps.reports_core.filters import Choice
    return Choice(value=user._id, display=None)


def _filter_by_parent_location_id(user, ui_filter):
    location = user.sql_location
    location_parent = location.parent.location_id if location and location.parent else None
    return ui_filter.value(**{ui_filter.name: location_parent,
                              'request_user': user})


AutoFilterConfig = namedtuple('AutoFilterConfig', ['slug', 'filter_function', 'short_description'])


def get_auto_filter_configurations():
    return [
        AutoFilterConfig('case_sharing_group', _filter_by_case_sharing_group_id,
                         _("The user's case sharing group")),
        AutoFilterConfig('location_id', _filter_by_location_id, _("The user's assigned location")),
        AutoFilterConfig('location_ids', _filter_by_location_ids, _("All of the user's assigned locations")),
        AutoFilterConfig('parent_location_id', _filter_by_parent_location_id,
                         _("The parent location of the user's assigned location")),
        AutoFilterConfig('username', _filter_by_username, _("The user's username")),
        AutoFilterConfig('user_id', _filter_by_user_id, _("The user's ID")),
    ]


def _get_auto_filter_function(slug):
    matched_configs = [config for config in get_auto_filter_configurations() if config.slug == slug]
    if not matched_configs:
        raise ValueError('Unexpected ID for AutoFilter', slug)
    else:
        assert len(matched_configs) == 1
        return matched_configs[0].filter_function


class AutoFilter(ReportAppFilter):
    filter_type = StringProperty(choices=[f.slug for f in get_auto_filter_configurations()])

    def get_filter_value(self, user, ui_filter):
        return _get_auto_filter_function(self.filter_type)(user, ui_filter)


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
        from corehq.apps.reports_core.filters import REQUEST_USER_KEY

        kwargs = {REQUEST_USER_KEY: user}
        try:
            ancestor = user.sql_location.get_ancestors(include_self=True).\
                get(location_type__name=self.ancestor_location_type_name)
            kwargs[ui_filter.name] = ancestor.location_id
        except (AttributeError, SQLLocation.DoesNotExist):
            # user.sql_location is None, or location does not have an ancestor of that type
            pass

        return ui_filter.value(**kwargs)


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
    # ID of the ReportConfiguration
    report_id = StringProperty(required=True)
    header = DictProperty()
    localized_description = DictProperty()
    xpath_description = StringProperty()
    use_xpath_description = BooleanProperty(default=False)
    show_data_table = BooleanProperty(default=True)
    complete_graph_configs = DictProperty(GraphConfiguration)

    filters = SchemaDictProperty(ReportAppFilter)
    # Unique ID of this mobile report config
    uuid = StringProperty(required=True)
    report_slug = StringProperty(required=False)  # optional, user-provided
    sync_delay = DecimalProperty(default=0.0)  # in hours

    _report = None

    def __init__(self, *args, **kwargs):
        super(ReportAppConfig, self).__init__(*args, **kwargs)
        if not self.uuid:
            self.uuid = uuid.uuid4().hex

    @classmethod
    def wrap(cls, doc):
        # for backwards compatibility with apps that have localized or xpath descriptions
        old_description = doc.get('description')
        if old_description:
            if isinstance(old_description, six.string_types) and not doc.get('xpath_description'):
                soft_assert_type_text(old_description)
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

    @property
    def instance_id(self):
        return self.report_slug or self.uuid


class ReportModule(ModuleBase):
    """
    Module for user configurable reports
    """

    module_type = 'report'

    report_configs = SchemaListProperty(ReportAppConfig)
    forms = []
    _loaded = False
    put_in_root = False

    @property
    @memoized
    def reports(self):
        from corehq.apps.userreports.models import get_report_configs
        return get_report_configs([r.report_id for r in self.report_configs], self.get_app().domain)

    @classmethod
    def new_module(cls, name, lang):
        module = ReportModule(
            name={(lang or 'en'): name or _("Reports")},
            case_type='',
        )
        module.get_or_create_unique_id()
        return module

    def get_details(self):
        from corehq.apps.app_manager.suite_xml.features.mobile_ucr import ReportModuleSuiteHelper
        return ReportModuleSuiteHelper(self).get_details()

    def get_custom_entries(self):
        from corehq.apps.app_manager.suite_xml.features.mobile_ucr import ReportModuleSuiteHelper
        return ReportModuleSuiteHelper(self).get_custom_entries()

    def get_menus(self, supports_module_filter=False, build_profile_id=None):
        from corehq.apps.app_manager.suite_xml.utils import get_module_enum_text, get_module_locale_id
        kwargs = {}
        if supports_module_filter:
            kwargs['relevant'] = interpolate_xpath(self.module_filter)

        menu = suite_models.LocalizedMenu(
            id=id_strings.menu_id(self),
            menu_locale_id=get_module_locale_id(self),
            menu_enum_text=get_module_enum_text(self),
            media_image=self.uses_image(build_profile_id=build_profile_id),
            media_audio=self.uses_audio(build_profile_id=build_profile_id),
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

    @property
    def validator(self):
        return ReportModuleValidator(self)


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
    case_list = SchemaProperty(CaseList)
    referral_list = SchemaProperty(CaseList)
    task_list = SchemaProperty(CaseList)
    parent_select = SchemaProperty(ParentSelect)
    search_config = SchemaProperty(CaseSearch)

    get_forms = IndexedSchema.Getter('forms')

    @classmethod
    def wrap(cls, data):
        data = cls.wrap_details(data)
        return super(ShadowModule, cls).wrap(data)

    @property
    def source_module(self):
        if self.source_module_id:
            try:
                return self._parent.get_module_by_unique_id(self.source_module_id)
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
                header={(lang or 'en'): _("Name")},
                field='name',
                model='case',
            )]
        )
        module = ShadowModule(
            name={(lang or 'en'): name or _("Untitled Module")},
            case_details=DetailPair(
                short=Detail(detail.to_json()),
                long=Detail(detail.to_json()),
            ),
        )
        module.get_or_create_unique_id()
        return module

    @property
    def validator(self):
        return ShadowModuleValidator(self)


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
            if cls._migrating_blobs_from_couch:
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
                if isinstance(attachment, six.text_type):
                    attachment = attachment.encode('utf-8')
                if isinstance(attachment, bytes):
                    info = {"content": attachment}
                else:
                    raise ValueError("Unknown attachment format: {!r}"
                                     .format(attachment))
                self.lazy_put_attachment(name=name, **info)
        return self

    def __attachment_cache_key(self, name):
        return 'lazy_attachment/{id}/{name}'.format(id=self.get_id, name=name)

    def __set_cached_attachment(self, name, content, timeout=60*60*24):
        cache.set(self.__attachment_cache_key(name), content, timeout=timeout)
        self._LAZY_ATTACHMENTS_CACHE[name] = content

    def __get_cached_attachment(self, name):
        try:
            # it has been fetched already during this request
            content = self._LAZY_ATTACHMENTS_CACHE[name]
        except KeyError:
            try:
                content = cache.get(self.__attachment_cache_key(name))
            except TypeError:
                # TODO - remove try/except sometime after Python 3 migration is complete
                return None
            if content is not None:
                if isinstance(content, six.text_type):
                    return None
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

    @property
    def master_id(self):
        """Return the ID of the 'master' app. For app builds this is the ID
        of the app they were built from otherwise it's just the app's ID."""
        return self.copy_of or self._id

    def save(self, response_json=None, increment_version=None, **params):
        if increment_version is None:
            increment_version = not self.copy_of and self.doc_type != 'LinkedApplication'
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
        _attachments = self.get_attachments()

        # the '_attachments' value is a dict of `name: blob_content`
        # pairs, and is part of the exported (serialized) app interface
        source['_attachments'] = {k: v.decode('utf-8') for (k, v) in _attachments.items()}
        source.pop("external_blobs", None)
        source = self.scrub_source(source)

        return json.dumps(source) if dump_json else source

    def get_attachments(self):
        attachments = {}
        for name in self.lazy_list_attachments():
            if re.match(ATTACHMENT_REGEX, name):
                # FIXME loss of metadata (content type, etc.)
                attachments[name] = self.lazy_fetch_attachment(name)
        return attachments

    def save_attachments(self, attachments, save=None):
        with self.atomic_blobs(save=save):
            for name, attachment in attachments.items():
                if re.match(ATTACHMENT_REGEX, name):
                    self.put_attachment(attachment, name)
        return self

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
    practice_mobile_worker_id = StringProperty()

    def __eq__(self, other):
        return self.langs == other.langs and self.practice_mobile_worker_id == other.practice_mobile_worker_id

    def __ne__(self, other):
        return not self.__eq__(other)


class ApplicationBase(VersionedDoc, SnapshotMixin,
                      CommCareFeatureSupportMixin,
                      CommentMixin):
    """
    Abstract base class for Application and RemoteApp.
    Contains methods for generating the various files and zipping them into CommCare.jar

    See note at top of file for high-level overview.
    """

    _blobdb_type_code = CODES.application
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
    is_auto_generated = BooleanProperty(default=False)
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
    vellum_case_management = BooleanProperty(default=True)

    # legacy property; kept around to be able to identify (deprecated) v1 apps
    application_version = StringProperty(default=APP_V2, choices=[APP_V1, APP_V2], required=False)
    last_modified = DateTimeProperty()

    def assert_app_v2(self):
        assert self.application_version == APP_V2

    build_profiles = SchemaDictProperty(BuildProfile)
    practice_mobile_worker_id = StringProperty()

    use_j2me_endpoint = BooleanProperty(default=False)

    # use commcare_flavor to avoid checking for none
    target_commcare_flavor = StringProperty(
        default='none',
        choices=['none', TARGET_COMMCARE, TARGET_COMMCARE_LTS]
    )

    # Whether or not the Application has had any forms submitted against it
    has_submissions = BooleanProperty(default=False)

    # domains that are allowed to have linked apps with this master
    linked_whitelist = StringListProperty()

    mobile_ucr_restore_version = StringProperty(
        default=MOBILE_UCR_VERSION_1, choices=MOBILE_UCR_VERSIONS, required=False
    )
    location_fixture_restore = StringProperty(
        default=DEFAULT_LOCATION_FIXTURE_OPTION, choices=LOCATION_FIXTURE_OPTIONS,
        required=False
    )

    @staticmethod
    def _scrap_old_conventions(data):
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
        if "built_with" in data and isinstance(data['built_with'], six.string_types):
            soft_assert_type_text(data['built_with'])
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
        return should_save

    @classmethod
    def wrap(cls, data, scrap_old_conventions=True):
        if scrap_old_conventions:
            should_save = cls._scrap_old_conventions(data)
        data["description"] = data.get('description') or data.get('short_description')

        self = super(ApplicationBase, cls).wrap(data)
        if not self.build_spec or self.build_spec.is_null():
            self.build_spec = get_default_build_spec()

        if scrap_old_conventions and should_save:
            self.save()

        return self

    @property
    @memoized
    def global_app_config(self):
        return GlobalAppConfig.for_app(self)

    def rename_lang(self, old_lang, new_lang):
        validate_lang(new_lang)

    def is_remote_app(self):
        return False

    @memoized
    def get_previous_version(self):
        return self.view('app_manager/applications',
            startkey=[self.domain, self.master_id, {}],
            endkey=[self.domain, self.master_id],
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
        salt = os.urandom(5)
        self.admin_password = make_password(raw_password, salt=salt)

        if raw_password.isnumeric():
            self.admin_password_charset = 'n'
        elif raw_password.isalnum():
            self.admin_password_charset = 'a'
        else:
            self.admin_password_charset = 'x'

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
    def heartbeat_url(self):
        return reverse('phone_heartbeat', args=[self.domain, self.get_id])

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

    @absolute_url_property
    def recovery_measures_url(self):
        return reverse('recovery_measures', args=[self.domain, self._id])

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
    def jad_settings(self):
        settings = {
            'JavaRosa-Admin-Password': self.admin_password,
            'Profile': self.profile_loc,
            'MIDlet-Jar-URL': self.jar_url,
            #'MIDlet-Name': self.name,
            # e.g. 2011-Apr-11 20:45
            'CommCare-Release': "true",
        }
        if not self.build_version or self.build_version < LooseVersion('2.8'):
            settings['Build-Number'] = self.version
        return settings

    def create_build_files(self, build_profile_id=None):
        all_files = self.create_all_files(build_profile_id)
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
            except (ResourceNotFound, KeyError):
                all_files = {
                    filename[len('files/'):]: self.lazy_fetch_attachment(filename)
                    for filename in self.blobs if filename.startswith('files/')
                }
                all_files = {
                    name: (contents if isinstance(contents, (bytes, SafeBytes)) else contents.encode('utf-8'))
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

    @property
    @memoized
    def timing_context(self):
        return TimingContext(self.name)

    def validate_app(self):
        return ApplicationBaseValidator(self).validate_app()

    @absolute_url_property
    def odk_profile_url(self):
        return reverse('download_odk_profile', args=[self.domain, self._id])

    @absolute_url_property
    def odk_media_profile_url(self):
        return reverse('download_odk_media_profile', args=[self.domain, self._id])

    def get_odk_qr_code(self, with_media=False, build_profile_id=None, download_target_version=False):
        """Returns a QR code, as a PNG to install on CC-ODK"""
        filename = 'qrcode.png' if not download_target_version else 'qrcode-targeted.png'
        try:
            return self.lazy_fetch_attachment(filename)
        except ResourceNotFound:
            url = self.odk_profile_url if not with_media else self.odk_media_profile_url
            kwargs = []
            if build_profile_id is not None:
                kwargs.append('profile={profile_id}'.format(profile_id=build_profile_id))
            if download_target_version:
                kwargs.append('download_target_version=true')
            url += '?' + '&'.join(kwargs)

            image = qrcode.make(url)
            output = BytesIO()
            image.save(output, "PNG")
            qr_content = output.getvalue()
            self.lazy_put_attachment(qr_content, filename,
                                     content_type="image/png")
            return qr_content

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

    @time_method()
    def make_build(self, comment=None, user_id=None):
        copy = super(ApplicationBase, self).make_build()
        if not copy._id:
            # I expect this always to be the case
            # but check explicitly so as not to change the _id if it exists
            copy._id = uuid.uuid4().hex

        copy.create_build_files()

        # since this hard to put in a test
        # I'm putting this assert here if copy._id is ever None
        # which makes tests error
        assert copy._id

        built_on = datetime.datetime.utcnow()
        copy.date_created = built_on
        copy.built_on = built_on
        copy.built_with = BuildRecord(
            version=copy.build_spec.version,
            build_number=copy.version,
            datetime=built_on,
        )
        copy.build_comment = comment
        copy.comment_from = user_id
        copy.is_released = False

        prune_auto_generated_builds.delay(self.domain, self._id)

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
        from corehq.apps.analytics.tasks import track_workflow, send_hubspot_form, HUBSPOT_SAVED_APP_FORM_ID
        self.last_modified = datetime.datetime.utcnow()
        if not self._rev and not domain_has_apps(self.domain):
            domain_has_apps.clear(self.domain)

        LatestAppInfo(self.master_id, self.domain).clear_caches()

        get_all_case_properties.clear(self)
        get_usercase_properties.clear(self)

        request = view_utils.get_request()
        user = getattr(request, 'couch_user', None)
        if user and user.days_since_created == 0:
            track_workflow(user.get_email(), 'Saved the App Builder within first 24 hours')
        send_hubspot_form(HUBSPOT_SAVED_APP_FORM_ID, request)
        if self.copy_of:
            cache.delete('app_build_cache_{}_{}'.format(self.domain, self.get_id))
        super(ApplicationBase, self).save(
            response_json=response_json, increment_version=increment_version, **params)

    @classmethod
    def save_docs(cls, docs, **kwargs):
        utcnow = datetime.datetime.utcnow()
        for doc in docs:
            doc['last_modified'] = utcnow
        super(ApplicationBase, cls).save_docs(docs, **kwargs)

    bulk_save = save_docs

    def set_form_versions(self):
        # by default doing nothing here is fine.
        pass

    def set_media_versions(self):
        pass

    def get_build_langs(self, build_profile_id=None):
        if build_profile_id is not None:
            return self.build_profiles[build_profile_id].langs
        else:
            return self.langs

    def convert_to_application(self):
        self.doc_type = 'Application'
        del self.master
        del self.linked_app_translations
        del self.linked_app_logo_refs
        del self.linked_app_attrs
        del self.uses_master_app_form_ids

    @property
    def commcare_flavor(self):
        return None if self.target_commcare_flavor == "none" else self.target_commcare_flavor


def validate_lang(lang):
    if not re.match(r'^[a-z]{2,3}(-[a-z]*)?$', lang):
        raise ValueError("Invalid Language")


class SavedAppBuild(ApplicationBase):
    def releases_list_json(self, timezone):
        """
        returns minimum possible data that could be used to list a Build on releases page on HQ

        :param timezone: timezone expected for timestamps in result
        :return: data dict
        """
        data = super(SavedAppBuild, self).to_json().copy()
        # ignore details that are not used
        for key in ('modules', 'user_registration', 'external_blobs',
                    '_attachments', 'profile', 'translations',
                    'description', 'short_description', 'multimedia_map', 'media_language_map'):
            data.pop(key, None)
        built_on_user_time = ServerTime(self.built_on).user_time(timezone)
        menu_item_label = self.built_with.get_menu_item_label()
        data.update({
            'id': self.id,
            'built_on_date': built_on_user_time.ui_string(USER_DATE_FORMAT),
            'built_on_time': built_on_user_time.ui_string(USER_TIME_FORMAT),
            'menu_item_label': menu_item_label,
            'jar_path': self.get_jar_path(),
            'short_name': self.short_name,
            'enable_offline_install': self.enable_offline_install,
            'include_media': self.doc_type != 'RemoteApp',
            'j2me_enabled': menu_item_label in CommCareBuildConfig.j2me_enabled_config_labels(),
            'commcare_flavor': (
                self.commcare_flavor
                if toggles.TARGET_COMMCARE_FLAVOR.enabled(self.domain) else None
            ),
        })
        comment_from = data['comment_from']
        if comment_from:
            data['comment_user_name'] = get_display_name_for_user_id(
                self.domain, comment_from, default=comment_from)

        return data


class Application(ApplicationBase, TranslationMixin, ApplicationMediaMixin,
                  ApplicationIntegrationMixin):
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
                                          choices=list(app_strings.CHOICES.keys()))
    auto_gps_capture = BooleanProperty(default=False)
    date_created = DateTimeProperty()
    created_from_template = StringProperty()
    use_grid_menus = BooleanProperty(default=False)
    grid_form_menus = StringProperty(default='none',
                                     choices=['none', 'all', 'some'])
    add_ons = DictProperty()
    smart_lang_display = BooleanProperty()  # null means none set so don't default to false/true

    def has_modules(self):
        return len(self.modules) > 0 and not self.is_remote_app()

    @property
    @memoized
    def commtrack_enabled(self):
        if settings.UNIT_TESTING:
            return False  # override with .tests.util.commtrack_enabled
        domain_obj = Domain.get_by_name(self.domain) if self.domain else None
        return domain_obj.commtrack_enabled if domain_obj else False

    @classmethod
    def wrap(cls, data):
        data.pop('commtrack_enabled', None)  # Remove me after migrating apps
        data.pop('media_language_map', None)
        data['modules'] = [module for module in data.get('modules', [])
                           if module.get('doc_type') != 'CareplanModule']
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
        from couchforms.analytics import get_form_analytics_metadata
        for xmlns in self.get_xmlns_map():
            get_form_analytics_metadata.clear(self.domain, self._id, xmlns)
        signals.app_post_save.send(Application, application=self)

    def make_reversion_to_copy(self, copy):
        app = super(Application, self).make_reversion_to_copy(copy)

        for form in app.get_forms():
            # reset the form's validation cache, since the form content is
            # likely to have changed in the revert!
            form.clear_validation_cache()
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
        return form.validate_form().render_xform(build_profile_id)

    def set_form_versions(self):
        """
        Set the 'version' property on each form as follows to the current app version if the form is new
        or has changed since the last build. Otherwise set it to the version from the last build.
        """
        def _hash(val):
            return hashlib.md5(val).hexdigest()

        previous_version = self.get_previous_version()
        if previous_version:
            force_new_version = self.build_profiles != previous_version.build_profiles
            for form_stuff in self.get_forms(bare=False):
                filename = 'files/%s' % self.get_form_filename(**form_stuff)
                form = form_stuff["form"]
                if not force_new_version:
                    try:
                        previous_form = previous_version.get_form(form.unique_id)
                        # take the previous version's compiled form as-is
                        # (generation code may have changed since last build)
                        previous_source = previous_version.fetch_attachment(filename)
                    except (ResourceNotFound, FormNotFoundException):
                        form.version = None
                    else:
                        previous_hash = _hash(previous_source)

                        # hack - temporarily set my version to the previous version
                        # so that that's not treated as the diff
                        previous_form_version = previous_form.get_version()
                        form.version = previous_form_version
                        my_hash = _hash(self.fetch_xform(form=form))
                        if previous_hash != my_hash:
                            form.version = None
                else:
                    form.version = None

    def set_media_versions(self):
        """
        Set the media version numbers for all media in the app to the current app version
        if the media is new or has changed since the last build. Otherwise set it to the
        version from the last build.
        """

        # access to .multimedia_map is slow
        previous_version = self.get_previous_version()
        prev_multimedia_map = previous_version.multimedia_map if previous_version else {}

        for path, map_item in six.iteritems(self.multimedia_map):
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

    @time_method()
    def create_profile(self, is_odk=False, with_media=False,
                       template='app_manager/profile.xml', build_profile_id=None, commcare_flavor=None):
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
                    'force': True,
                    'value': self.logo_refs[logo_name]['path'],
                }

        if toggles.MOBILE_RECOVERY_MEASURES.enabled(self.domain):
            app_profile['properties']['recovery-measures-url'] = {
                'force': True,
                'value': self.recovery_measures_url,
            }

        if with_media:
            profile_url = self.media_profile_url if not is_odk else (self.odk_media_profile_url + '?latest=true')
        else:
            profile_url = self.profile_url if not is_odk else (self.odk_profile_url + '?latest=true')

        if toggles.CUSTOM_PROPERTIES.enabled(self.domain) and "custom_properties" in self__profile:
            app_profile['custom_properties'].update(self__profile['custom_properties'])

        apk_heartbeat_url = self.heartbeat_url
        locale = self.get_build_langs(build_profile_id)[0]
        target_package_id = {
            TARGET_COMMCARE: 'org.commcare.dalvik',
            TARGET_COMMCARE_LTS: 'org.commcare.lts',
        }.get(commcare_flavor)
        return render_to_string(template, {
            'is_odk': is_odk,
            'app': self,
            'profile_url': profile_url,
            'app_profile': app_profile,
            'cc_user_domain': cc_user_domain(self.domain),
            'include_media_suite': with_media,
            'uniqueid': self.master_id,
            'name': self.name,
            'descriptor': "Profile File",
            'build_profile_id': build_profile_id,
            'locale': locale,
            'apk_heartbeat_url': apk_heartbeat_url,
            'target_package_id': target_package_id,
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

    @memoized
    def get_practice_user_id(self, build_profile_id=None):
        # returns app or build profile specific practice_mobile_worker_id
        if build_profile_id:
            build_spec = self.build_profiles[build_profile_id]
            return build_spec.practice_mobile_worker_id
        else:
            return self.practice_mobile_worker_id

    @property
    @memoized
    def enable_practice_users(self):
        return (
            self.supports_practice_users and
            domain_has_privilege(self.domain, privileges.PRACTICE_MOBILE_WORKERS)
        )

    @property
    @memoized
    def enable_update_prompts(self):
        return (
            # custom for ICDS until ICDS users are > 2.38
            (self.supports_update_prompts or toggles.ICDS.enabled(self.domain)) and
            toggles.PHONE_HEARTBEAT.enabled(self.domain)
        )

    @memoized
    def get_practice_user(self, build_profile_id=None):
        """
        kwargs:
            build_profile_id: id of a particular build profile to get the practice user for
                If it's None, practice user of the default app is returned

        Returns:
            App or build profile specific practice user and validates that the user is
                a practice mode user and that user belongs to app.domain

        This is memoized to avoid refetching user when validating app, creating build files and
            generating suite file.
        """
        practice_user_id = self.get_practice_user_id(build_profile_id=build_profile_id)
        if practice_user_id:
            return get_and_assert_practice_user_in_domain(practice_user_id, self.domain)
        else:
            return None

    @time_method()
    def create_practice_user_restore(self, build_profile_id=None):
        """
        Returns:
            Returns restore xml as a string for the practice user of app or
                app profile specfied by build_profile_id
            Raises a PracticeUserException if the user is not practice user
        """
        from corehq.apps.ota.models import DemoUserRestore
        if not self.enable_practice_users:
            return None
        user = self.get_practice_user(build_profile_id)
        if user:
            user_restore = DemoUserRestore.objects.get(id=user.demo_restore_id)
            return user_restore.get_restore_as_string()
        else:
            return None

    @classmethod
    def get_form_filename(cls, type=None, form=None, module=None):
        return 'modules-%s/forms-%s.xml' % (module.id, form.id)

    @time_method()
    def _make_language_files(self, prefix, build_profile_id):
        return {
            "{}{}/app_strings.txt".format(prefix, lang): self.create_app_strings(lang, build_profile_id).encode('utf-8')
            for lang in ['default'] + self.get_build_langs(build_profile_id)
        }

    @time_method()
    def _get_form_files(self, prefix, build_profile_id):
        files = {}
        for form_stuff in self.get_forms(bare=False):
            def exclude_form(form):
                return isinstance(form, ShadowForm) or form.is_a_disabled_release_form()

            if not exclude_form(form_stuff['form']):
                filename = prefix + self.get_form_filename(**form_stuff)
                form = form_stuff['form']
                try:
                    files[filename] = self.fetch_xform(form=form, build_profile_id=build_profile_id)
                except XFormValidationFailed:
                    raise XFormException(_('Unable to validate the forms due to a server error. '
                                           'Please try again later.'))
                except XFormException as e:
                    raise XFormException(_('Error in form "{}": {}').format(trans(form.name), six.text_type(e)))
        return files

    @time_method()
    @memoized
    def create_all_files(self, build_profile_id=None):
        self.set_form_versions()
        self.set_media_versions()
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
        if self.commcare_flavor:
            files['{}profile-{}.xml'.format(prefix, self.commcare_flavor)] = self.create_profile(
                is_odk=False,
                build_profile_id=build_profile_id,
                commcare_flavor=self.commcare_flavor,
            )
            files['{}profile-{}.ccpr'.format(prefix, self.commcare_flavor)] = self.create_profile(
                is_odk=True,
                build_profile_id=build_profile_id,
                commcare_flavor=self.commcare_flavor,
            )
            files['{}media_profile-{}.xml'.format(prefix, self.commcare_flavor)] = self.create_profile(
                is_odk=False,
                with_media=True,
                build_profile_id=build_profile_id,
                commcare_flavor=self.commcare_flavor,
            )
            files['{}media_profile-{}.ccpr'.format(prefix, self.commcare_flavor)] = self.create_profile(
                is_odk=True,
                with_media=True,
                build_profile_id=build_profile_id,
                commcare_flavor=self.commcare_flavor,
            )

        practice_user_restore = self.create_practice_user_restore(build_profile_id)
        if practice_user_restore:
            files.update({
                '{}practice_user_restore.xml'.format(prefix): practice_user_restore
            })

        files.update(self._make_language_files(prefix, build_profile_id))
        files.update(self._get_form_files(prefix, build_profile_id))
        return files

    get_modules = IndexedSchema.Getter('modules')

    @parse_int([1])
    def get_module(self, i):
        try:
            return self.modules[i].with_id(i % len(self.modules), self)
        except IndexError:
            raise ModuleNotFoundException(_("Could not find module with index {}".format(i)))

    def get_module_by_unique_id(self, unique_id, error=''):
        def matches(module):
            return module.get_or_create_unique_id() == unique_id
        for obj in self.get_modules():
            if matches(obj):
                return obj
        if not error:
            error = _("Could not find module with ID='{unique_id}' in app '{app_name}'.").format(
                app_name=self.name, unique_id=unique_id)
        raise ModuleNotFoundException(error)

    def get_module_index(self, unique_id):
        for index, module in enumerate(self.get_modules()):
            if module.unique_id == unique_id:
                return index
        error = _("Could not find module with ID='{unique_id}' in app '{app_name}'.").format(
            app_name=self.name, unique_id=unique_id)
        raise ModuleNotFoundException(error)

    def get_report_modules(self):
        for module in self.modules:
            if isinstance(module, ReportModule):
                yield module

    def get_forms(self, bare=True):
        for module in self.get_modules():
            for form in module.get_forms():
                yield form if bare else {
                    'type': 'module_form',
                    'module': module,
                    'form': form
                }

    def get_form(self, form_unique_id, bare=True):
        def matches(form):
            return form.get_unique_id() == form_unique_id
        for obj in self.get_forms(bare):
            if matches(obj if bare else obj['form']):
                return obj
        raise FormNotFoundException(
            ("Form in app '%s' with unique id '%s' not found"
             % (self.id, form_unique_id)))

    def get_form_location(self, form_unique_id):
        for m_index, module in enumerate(self.get_modules()):
            for f_index, form in enumerate(module.get_forms()):
                if form_unique_id == form.unique_id:
                    return m_index, f_index
        raise KeyError("Form in app '%s' with unique id '%s' not found" % (self.id, form_unique_id))

    @classmethod
    def new_app(cls, domain, name, lang="en"):
        app = cls(domain=domain, modules=[], name=name, langs=[lang], date_created=datetime.datetime.utcnow())
        return app

    def add_module(self, module):
        self.modules.append(module)
        return self.get_module(-1)

    def delete_module(self, module_unique_id):
        module = self.get_module_by_unique_id(module_unique_id)
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

    def new_form(self, module_id, name, lang, attachment=Ellipsis):
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
        for i, lang in enumerate(self.langs):
            if lang == old_lang:
                self.langs[i] = new_lang
        for profile in self.build_profiles:
            for i, lang in enumerate(profile.langs):
                if lang == old_lang:
                    profile.langs[i] = new_lang
        for module in self.get_modules():
            module.rename_lang(old_lang, new_lang)
        _rename_key(self.translations, old_lang, new_lang)

    def rearrange_modules(self, from_index, to_index):
        modules = self.modules
        try:
            if toggles.LEGACY_CHILD_MODULES.enabled(self.domain):
                modules.insert(to_index, modules.pop(from_index))
            else:
                # remove module
                moving_module = modules.pop(from_index)

                # remove its children
                children = [m for m in modules if m.root_module_id == moving_module.unique_id]
                modules = [m for m in modules if m.root_module_id != moving_module.unique_id]

                # add back in module and children
                modules = modules[:to_index] + [moving_module] + children + modules[to_index:]
        except IndexError:
            raise RearrangeError()
        self.modules = modules

    def rearrange_forms(self, from_module_uid, to_module_uid, from_index, to_index):
        """
        The case type of the two modules conflict, the rearrangement goes through anyway.
        This is intentional.

        """
        from_module = self.get_module_by_unique_id(from_module_uid)
        to_module = self.get_module_by_unique_id(to_module_uid)
        try:
            from_module.forms[from_index].pre_move_hook(from_module, to_module)
        except NotImplementedError:
            pass
        try:
            form = from_module.forms.pop(from_index)
            if not isinstance(form, AdvancedForm):
                if from_module.is_surveys != to_module.is_surveys:
                    if from_module.is_surveys:
                        form.requires = "case"
                        form.actions.update_case = UpdateCaseAction(
                            condition=FormActionCondition(type='always'))
                    else:
                        form.requires = "none"
                        form.actions.update_case = UpdateCaseAction(
                            condition=FormActionCondition(type='never'))
            to_module.add_insert_form(from_module, form, index=to_index, with_source=True)
        except IndexError:
            raise RearrangeError()

    def move_child_modules_after_parents(self):
        # This makes the module ordering compatible with the front-end display
        modules_by_parent_id = OrderedDict(
            (m.unique_id, [m]) for m in self.modules if not m.root_module_id
        )
        orphaned_modules = []
        for module in self.modules:
            if module.root_module_id:
                if module.root_module_id in modules_by_parent_id:
                    modules_by_parent_id[module.root_module_id].append(module)
                else:
                    orphaned_modules.append(module)

        normal_modules = [m for modules in modules_by_parent_id.values() for m in modules]
        self.modules = normal_modules + orphaned_modules

    def scrub_source(self, source):
        source = update_form_unique_ids(source)
        return update_report_module_ids(source)

    def copy_form(self, from_module, form, to_module, rename=False):
        """
        The case type of the two modules conflict,
        copying (confusingly) is still allowed.
        This is intentional.

        """
        copy_source = deepcopy(form.to_json())
        # only one form can be a release notes form, so set them to False explicitly when copying
        copy_source['is_release_notes_form'] = False
        copy_source['enable_release_notes'] = False
        if 'unique_id' in copy_source:
            del copy_source['unique_id']

        if rename:
            for lang, name in six.iteritems(copy_source['name']):
                with override(lang):
                    copy_source['name'][lang] = _('Copy of {name}').format(name=name)

        copy_form = to_module.add_insert_form(from_module, FormBase.wrap(copy_source))
        to_app = to_module.get_app()
        save_xform(to_app, copy_form, form.source.encode('utf-8'))

        return copy_form

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

    def get_forms_by_xmlns(self, xmlns, log_missing=True):
        """
        Return the forms with the given xmlns.
        This function could return multiple forms if there are shadow forms in the app.
        """
        if xmlns == "http://code.javarosa.org/devicereport":
            return []
        forms = self.get_xmlns_map()[xmlns]
        if len(forms) < 1:
            if log_missing:
                logging.error('App %s in domain %s has %s forms with xmlns %s' % (
                    self.get_id,
                    self.domain,
                    len(forms),
                    xmlns,
                ))
            return []
        non_shadow_forms = [form for form in forms if form.form_type != 'shadow_form']
        assert len(non_shadow_forms) <= 1
        return forms

    def get_xform_by_xmlns(self, xmlns, log_missing=True):
        forms = self.get_forms_by_xmlns(xmlns, log_missing)
        if not forms:
            return None
        else:
            # If there are multiple forms with the same xmlns, then all but one are shadow forms, therefore they
            # all have the same xform.
            return forms[0].wrapped_xform()


    def get_questions(self, xmlns, langs=None, include_triggers=False, include_groups=False,
                      include_translations=False):
        forms = self.get_forms_by_xmlns(xmlns)
        if not forms:
            return []
        # If there are multiple forms with the same xmlns, then some of them are shadow forms, so all the questions
        # will be the same.
        return forms[0].get_questions(langs or self.langs, include_triggers, include_groups, include_translations)

    def validate_app(self):
        return ApplicationValidator(self).validate_app()

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
        if not self.build_version or self.build_version < LooseVersion(yaml_setting.get("since", "0")):
            setting = yaml_setting.get("disabled_default", None)
            if setting is not None:
                return setting
        return yaml_setting.get("default")

    @quickcache(['self._id', 'self.version'])
    def get_case_metadata(self):
        from corehq.apps.app_manager.app_schemas.app_case_metadata import AppCaseMetadataBuilder
        return AppCaseMetadataBuilder(self.domain, self).case_metadata()

    def get_subcase_types(self, case_type):
        """
        Return the subcase types defined across an app for the given case type
        """
        return {t for m in self.get_modules()
                if m.case_type == case_type
                for t in m.get_subcase_types()}

    @memoized
    def grid_display_for_some_modules(self):
        return self.grid_form_menus == 'some'

    @memoized
    def grid_display_for_all_modules(self):
        return self.grid_form_menus == 'all'


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
            if len(list(self.build_profiles.keys())) > 1:
                raise AppEditingError('More than one app profile for a remote app')
            else:
                # return first profile, generated as part of lazy migration
                return self.build_profiles[list(self.build_profiles.keys())[0]].langs
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
            raise AppEditingError(_('Problem loading suite file from profile file. Is your profile file correct?'))

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
                    xform = XForm(fetch(location).decode('utf-8'))
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

    # The following properties will overwrite their corresponding values from
    # the master app everytime the new master is pulled
    linked_app_translations = DictProperty()  # corresponding property: translations
    linked_app_logo_refs = DictProperty()  # corresponding property: logo_refs
    linked_app_attrs = DictProperty()  # corresponds to app attributes

    SUPPORTED_SETTINGS = ['target_commcare_flavor', 'practice_mobile_worker_id']

    # if `uses_master_app_form_ids` is True, the form id might match the master's form id
    # from a bug years ago. These should be fixed when mobile can handle the change
    # https://manage.dimagi.com/default.asp?283410
    uses_master_app_form_ids = BooleanProperty(default=False)

    @property
    @memoized
    def domain_link(self):
        from corehq.apps.linked_domain.dbaccessors import get_domain_master_link
        return get_domain_master_link(self.domain)

    def get_master_version(self):
        if self.domain_link:
            return get_master_app_version(self.domain_link, self.master)

    @property
    def master_is_remote(self):
        if self.domain_link:
            return self.domain_link.is_remote

    def get_latest_master_release(self):
        if self.domain_link:
            return get_latest_master_app_release(self.domain_link, self.master)
        else:
            raise ActionNotPermitted

    def reapply_overrides(self):
        # Used by app_manager.views.utils.update_linked_app()
        self.translations.update(self.linked_app_translations)
        self.logo_refs.update(self.linked_app_logo_refs)
        for attribute, value in self.linked_app_attrs.items():
            setattr(self, attribute, value)
        for key, ref in self.logo_refs.items():
            mm = CommCareMultimedia.get(ref['m_id'])
            self.create_mapping(mm, ref['path'], save=False)
        self.save()


def import_app(app_id_or_source, domain, source_properties=None, request=None):
    if isinstance(app_id_or_source, six.string_types):
        soft_assert_type_text(app_id_or_source)
        app_id = app_id_or_source
        source = get_app(None, app_id)
        source_domain = source['domain']
        source = source.export_json(dump_json=False)
        report_map = get_static_report_mapping(source_domain, domain)
    else:
        cls = get_correct_app_class(app_id_or_source)
        # Don't modify original app source
        app = cls.wrap(deepcopy(app_id_or_source))
        source = app.export_json(dump_json=False)
        report_map = {}
    try:
        attachments = source['_attachments']
    except KeyError:
        attachments = {}
    finally:
        source['_attachments'] = {}
    if source_properties is not None:
        for key, value in six.iteritems(source_properties):
            source[key] = value
    cls = get_correct_app_class(source)
    # Allow the wrapper to update to the current default build_spec
    if 'build_spec' in source:
        del source['build_spec']
    app = cls.from_source(source, domain)
    app.date_created = datetime.datetime.utcnow()
    app.cloudcare_enabled = domain_has_privilege(domain, privileges.CLOUDCARE)

    if report_map:
        for module in app.get_report_modules():
            for config in module.report_configs:
                try:
                    config.report_id = report_map[config.report_id]
                except KeyError:
                    raise AppEditingError(
                        "Report {} not found in {}".format(config.report_id, domain)
                    )

    app.save_attachments(attachments)

    try:
        if not app.is_remote_app():
            for path, media in app.get_media_objects(remove_unused=True):
                if domain not in media.valid_domains:
                    media.valid_domains.append(domain)
                    media.save()
    except ReportConfigurationNotFoundError:
        if request:
            messages.warning(request, _("Copying the application succeeded, but the application will have errors "
                                        "because your application contains a Mobile Report Module that references "
                                        "a UCR configured in this project space. Multimedia may be absent."))

    if not app.is_remote_app():
        enable_usercase_if_necessary(app)

    return app


def enable_usercase_if_necessary(app):
    if any(module.uses_usercase() for module in app.get_modules()):
        from corehq.apps.app_manager.util import enable_usercase
        enable_usercase(app.domain)


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


class GlobalAppConfig(Document):
    # this should be the unique id of the app (not of a versioned copy)
    app_id = StringProperty()
    domain = StringProperty()

    # these let mobile prompt updates for application and APK
    app_prompt = StringProperty(
        choices=["off", "on", "forced"],
        default="off"
    )
    apk_prompt = StringProperty(
        choices=["off", "on", "forced"],
        default="off"
    )

    # corresponding versions to which user should be prompted to update to
    apk_version = StringProperty(default=LATEST_APK_VALUE)  # e.g. '2.38.0/latest'
    app_version = IntegerProperty(default=LATEST_APP_VALUE)

    @classmethod
    def for_app(cls, app):
        """
        Returns the actual config object for the app or an unsaved
            default object
        """
        app_id = app.master_id

        res = cls.get_db().view(
            "global_app_config_by_app_id/view",
            key=[app_id, app.domain],
            reduce=False,
            include_docs=True,
        ).one()

        if res:
            return cls(res['doc'])
        else:
            # return default config
            return cls(app_id=app_id, domain=app.domain)

    def save(self, *args, **kwargs):
        LatestAppInfo(self.app_id, self.domain).clear_caches()
        super(GlobalAppConfig, self).save(*args, **kwargs)


class AppReleaseByLocation(models.Model):
    domain = models.CharField(max_length=255, null=False)
    app_id = models.CharField(max_length=255, null=False)
    location = models.ForeignKey(SQLLocation, on_delete=models.CASCADE, to_field='location_id')
    build_id = models.CharField(max_length=255, null=False)
    version = models.IntegerField(null=False)
    active = models.BooleanField(default=True)
    activated_on = models.DateTimeField(null=True, blank=True)
    deactivated_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = (("domain", "build_id", "location", "version"),)

    def save(self, *args, **kwargs):
        super(AppReleaseByLocation, self).save(*args, **kwargs)
        expire_get_latest_app_release_by_location_cache(self)

    @property
    @memoized
    def build(self):
        return get_app(self.domain, self.build_id)

    def clean(self):
        if self.active:
            if not self.build.is_released:
                raise ValidationError({'version': _("Version {} not released. Please mark it as released to add "
                                                    "restrictions.").format(self.build.version)})
            enabled_release = get_latest_app_release_by_location(self.domain, self.location.location_id,
                                                                 self.app_id)
            if enabled_release and enabled_release.version > self.version:
                raise ValidationError({'version': _("Higher version {} already enabled for this application and "
                                                    "location").format(enabled_release.version)})

    @classmethod
    def update_status(cls, domain, app_id, build_id, location_id, version, active):
        """
        create a new object or just set the status of an existing one with provided
        domain, app_id, build_id, location_id and version to the status passed
        :param build_id: id of the build corresponding to the version
        """
        try:
            release = AppReleaseByLocation.objects.get(
                domain=domain, app_id=app_id, build_id=build_id, location_id=location_id, version=version
            )
        except cls.DoesNotExist:
            release = AppReleaseByLocation(
                domain=domain, app_id=app_id, build_id=build_id, location_id=location_id, version=version
            )
        release.activate() if active else release.deactivate()

    def deactivate(self):
        self.active = False
        self.deactivated_on = datetime.datetime.utcnow()
        self.full_clean()
        self.save()

    def activate(self):
        self.active = True
        self.activated_on = datetime.datetime.utcnow()
        self.full_clean()
        self.save()

    def to_json(self):
        return {
            'location': self.location.get_path_display(),
            'app': self.app_id,
            'build_id': self.build_id,
            'version': self.version,
            'active': self.active,
            'id': self._get_pk_val(),
            'activated_on': (datetime.datetime.strftime(self.activated_on, '%Y-%m-%d  %H:%M:%S')
                             if self.activated_on else None),
            'deactivated_on': (datetime.datetime.strftime(self.deactivated_on, '%Y-%m-%d %H:%M:%S')
                               if self.deactivated_on else None),
        }


class LatestEnabledBuildProfiles(models.Model):
    # ToDo: this would be deprecated after AppReleaseByLocation is released and
    # this model's entries are migrated to the new location specific model
    app_id = models.CharField(max_length=255)
    build_profile_id = models.CharField(max_length=255)
    version = models.IntegerField()
    build_id = models.CharField(max_length=255)
    active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        super(LatestEnabledBuildProfiles, self).save(*args, **kwargs)
        self.expire_cache(self.build.domain)

    @property
    def build(self):
        if not hasattr(self, '_build'):
            self._build = Application.get(self.build_id)
        return self._build

    def clean(self):
        if self.active:
            if not self.build.is_released:
                raise ValidationError({
                    'version': _("Version {} not released. Can not enable profiles for unreleased versions"
                                 ).format(self.build.version)
                })
            latest_enabled_build_profile = LatestEnabledBuildProfiles.for_app_and_profile(
                app_id=self.build.copy_of,
                build_profile_id=self.build_profile_id
            )
            if latest_enabled_build_profile and latest_enabled_build_profile.version > self.version:
                raise ValidationError({
                    'version': _("Latest version available for this profile is {}, which is "
                                 "higher than this version. Disable any higher versions first."
                                 ).format(latest_enabled_build_profile.version)})

    @classmethod
    def update_status(cls, build, build_profile_id, active):
        """
        create a new object or just set the status of an existing one for an app
        build and build profile to the status passed
        :param active: to be set as active, True/False
        """
        app_id = build.copy_of
        build_id = build.get_id
        version = build.version
        try:
            build_profile = LatestEnabledBuildProfiles.objects.get(
                app_id=app_id,
                version=version,
                build_profile_id=build_profile_id,
                build_id=build_id
            )
        except cls.DoesNotExist:
            build_profile = LatestEnabledBuildProfiles(
                app_id=app_id,
                version=version,
                build_profile_id=build_profile_id,
                build_id=build_id
            )
        # assign it to avoid re-fetching during validations
        build_profile._build = build
        build_profile.activate() if active else build_profile.deactivate()

    def activate(self):
        self.active = True
        self.full_clean()
        self.save()

    def deactivate(self):
        self.active = False
        self.full_clean()
        self.save()

    @classmethod
    def for_app_and_profile(cls, app_id, build_profile_id):
        return cls.objects.filter(
            app_id=app_id,
            build_profile_id=build_profile_id,
            active=True
        ).order_by('-version').first()

    def expire_cache(self, domain):
        get_latest_enabled_build_for_profile.clear(domain, self.build_profile_id)
        get_latest_enabled_versions_per_profile.clear(self.app_id)

    def to_json(self, app_names):
        from corehq.apps.app_manager.serializers import LatestEnabledBuildProfileSerializer
        return LatestEnabledBuildProfileSerializer(self, context={'app_names': app_names}).data


# backwards compatibility with suite-1.0.xml
FormBase.get_command_id = lambda self: id_strings.form_command(self)
FormBase.get_locale_id = lambda self: id_strings.form_locale(self)

ModuleBase.get_locale_id = lambda self: id_strings.module_locale(self)

ModuleBase.get_case_list_command_id = lambda self: id_strings.case_list_command(self)
ModuleBase.get_case_list_locale_id = lambda self: id_strings.case_list_locale(self)

Module.get_referral_list_command_id = lambda self: id_strings.referral_list_command(self)
Module.get_referral_list_locale_id = lambda self: id_strings.referral_list_locale(self)
