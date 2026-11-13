import json
import logging
import uuid
from collections import defaultdict
from copy import deepcopy

from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DictProperty,
    DocumentSchema,
    IntegerProperty,
    SchemaListProperty,
    SchemaProperty,
    StringListProperty,
    StringProperty,
)
from django.core.cache import cache
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from lxml import etree
from memoized import memoized

from corehq import toggles
from corehq.apps.app_manager import (
    const,
    id_strings,
)
from corehq.apps.app_manager.exceptions import (
    FormNotFoundException,
    ScheduleError,
    XFormException,
    XFormValidationError,
)
from corehq.apps.app_manager.helpers.validators import (
    AdvancedFormValidator,
    FormBaseValidator,
    FormValidator,
    IndexedFormBaseValidator,
    ShadowFormValidator,
)
from corehq.apps.app_manager.templatetags.xforms_extras import (
    clean_trans,
    trans,
)
from corehq.apps.app_manager.util import actions_use_usercase
from corehq.apps.app_manager.xform import XForm, validate_xform
from corehq.apps.hqmedia.models import FormMediaMixin
from corehq.util.quickcache import quickcache
from corehq.util.timer import time_method

from .base import (
    CustomAssertion,
    FormIdProperty,
    IndexedSchema,
    LabelProperty,
    rename_key,
)
from .form_actions import (
    AdvancedFormActions,
    ArbitraryDatum,
    CaseReferences,
    FormActionCondition,
    FormActions,
    LoadUpdateAction,
    OpenSubCaseAction,
    PreloadAction,
)
from .mixins import (
    CommentMixin,
    NavMenuItemMediaMixin,
)


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

        return source

    def __set__(self, form, value):
        unique_id = form.get_unique_id()
        app = form.get_app()
        filename = "%s.xml" % unique_id
        if isinstance(value, str):
            value = value.encode('utf-8')
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
        cache.set(key, value, 7 * 24 * 60 * 60)  # cache for 7 days


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
    FormLinks are advanced end of form navigation configuration, used when a module's
    post_form_workflow is WORKFLOW_FORM.

    They allow the user to specify one or more XPath expressions, each with either
    a module id or form id. The user will be sent to the first module/form whose
    expression evaluates to true. If none of the conditions is met, the workflow specified
    in the module's post_form_workflow_fallback is executed.

    xpath: XPath condition that must be true in order to execute link
    form_id: ID of next form to open, mutually exclusive with module_unique_id
    form_module_id: ID of the form's module (this is used for shadow modules)
    module_unique_id: ID of next module to open, mutually exclusive with form_id
    datums: Any user-provided datums, necessary when HQ can't figure them out automatically
    """
    xpath = StringProperty()
    form_id = FormIdProperty('modules[*].forms[*].form_links[*].form_id')
    form_module_id = StringProperty()
    module_unique_id = StringProperty()
    datums = SchemaListProperty(FormDatum)

    def get_unique_id(self, app):
        """"Get a unique ID for this link. For links to modules this is just the ID
        of the module since that is already unique in the app.

        For links to forms this is a combination of the form and module ID which is
        necessary to support linking to forms in shadow modules.
        """
        if self.module_unique_id:
            return self.module_unique_id

        if self.form_module_id:
            return f"{self.form_module_id}.{self.form_id}"

        # legacy data does not have 'form_module_id'
        form = app.get_form(self.form_id)
        return f"{form.get_module().unique_id}.{self.form_id}"


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


class FormBase(DocumentSchema):
    """
    Part of a Managed Application; configuration for a form.
    Translates to a second-level menu on the phone

    """
    form_type = None

    name = DictProperty(str)
    unique_id = StringProperty()
    show_count = BooleanProperty(default=False)
    xmlns = StringProperty()
    version = IntegerProperty()
    source = FormSource()
    validation_cache = CachedStringProperty(
        lambda self: "cache-%s-%s-validation" % (self.get_app().get_id, self.unique_id)
    )
    post_form_workflow = StringProperty(
        default=const.WORKFLOW_DEFAULT,
        choices=const.ALL_WORKFLOWS
    )
    post_form_workflow_fallback = StringProperty(
        choices=const.WORKFLOW_FALLBACK_OPTIONS,
        default=None,
    )
    auto_gps_capture = BooleanProperty(default=False)
    form_links = SchemaListProperty(FormLink)
    schedule_form_id = StringProperty(exclude_if_none=True)
    custom_assertions = SchemaListProperty(CustomAssertion)
    custom_instances = SchemaListProperty(CustomInstance)
    case_references_data = SchemaProperty(CaseReferences)
    is_release_notes_form = BooleanProperty(default=False)
    enable_release_notes = BooleanProperty(default=False)
    session_endpoint_id = StringProperty(exclude_if_none=True)  # See toggles.SESSION_ENDPOINTS
    respect_relevancy = BooleanProperty(default=True)

    # computed datums IDs that are allowed in endpoints
    function_datum_endpoints = StringListProperty()

    submit_label = LabelProperty(default={})
    submit_notification_label = LabelProperty(default={})

    def __repr__(self):
        return f"{self.doc_type}(id='{self.id}', name='{self.default_name()}', unique_id='{self.unique_id}')"

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

    @property
    def can_edit_in_vellum(self):
        return self.form_type != 'shadow_form'

    @case_references.setter
    def case_references(self, case_references):
        self.case_references_data = case_references

    def pre_delete_hook(self):
        raise NotImplementedError()

    def pre_move_hook(self, from_module, to_module):
        """ Called before a form is moved between modules or to a different position """
        raise NotImplementedError()

    def wrapped_xform(self):
        return XForm(self.source, domain=self.get_app().domain)

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
                    validate_xform(etree.tostring(form.xml, encoding='utf-8'))
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

    def validate_for_build(self):
        return self.validator.validate_for_build()

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
        xform.add_missing_instances(self, app)

    @memoized
    def render_xform(self, build_profile_id=None):
        xform = XForm(self.source, domain=self.get_app().domain)
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
    @quickcache(
        [
            'self.source',
            'langs',
            'include_triggers',
            'include_groups',
            'include_translations',
            'include_fixtures',
            'include_locked_status',
        ],
        timeout=24 * 60 * 60,
    )
    def get_questions(
        self,
        langs,
        include_triggers=False,
        include_groups=False,
        include_translations=False,
        include_fixtures=False,
        include_locked_status=False
    ):
        try:
            return XForm(self.source, domain=self.get_app().domain).get_questions(
                langs=langs,
                include_triggers=include_triggers,
                include_groups=include_groups,
                include_translations=include_translations,
                include_fixtures=include_fixtures,
                include_locked_status=include_locked_status,
            )
        except XFormException as e:
            raise XFormException(_('Error in form "{}": {}').format(trans(self.name), e))

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
                return "{}{}".format(const.ATTACHMENT_PREFIX, key)
            return key
        return format_key

    def rename_lang(self, old_lang, new_lang):
        rename_key(self.name, old_lang, new_lang)
        try:
            self.rename_xform_language(old_lang, new_lang)
        except XFormException:
            pass

    def rename_xform_language(self, old_code, new_code):
        source = XForm(self.source, domain=self.get_app().domain)
        if source.exists():
            source.rename_language(old_code, new_code)
            self.source = source.render().decode('utf-8')

    def default_name(self):
        app = self.get_app()
        return clean_trans(
            self.name,
            [app.default_language] + app.langs
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

    def is_auto_submitting_form(self, case_type=None):
        """
        Should return True if this form passes the following tests:
         * Requires a case of the same type
         * Pragma-Submit-Automatically is set
         * No question needs manual input
        """
        if case_type is None:
            return False

        if not self.requires_case():
            return False

        qs = self.get_questions([], include_triggers=True)
        return any(['label_ref' in q and q['label_ref'] == 'Pragma-Submit-Automatically' for q in qs])

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

    def get_submit_label(self, lang):
        if lang in self.submit_label:
            return self.submit_label[lang]
        return 'Submit'

    def get_submit_notification_label(self, lang):
        if self.submit_notification_label and lang in self.submit_notification_label:
            return self.submit_notification_label[lang]
        return ''


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


class Form(IndexedFormBase, FormMediaMixin, NavMenuItemMediaMixin):
    form_type = 'module_form'

    form_filter = StringProperty(exclude_if_none=True)
    requires = StringProperty(choices=["case", "referral", "none"], default="none")
    actions = SchemaProperty(FormActions)

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
        elif self.actions.open_case.condition.is_active() or self.actions.subcases:
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
            const.USERCASE_TYPE: {
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
            refs.load = {key: [value] for key, value in preload.items()}
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
                    self.actions.open_case.is_active()
                    or self.actions.update_case.is_active()
                    or self.actions.close_case.is_active()):
                case_relationships_by_child_type[child_case_type].add(
                    (parent_case_type, subcase.reference_id or 'parent'))
        return case_relationships_by_child_type


class AdvancedForm(IndexedFormBase, FormMediaMixin, NavMenuItemMediaMixin):
    form_type = 'advanced_form'
    form_filter = StringProperty()
    actions = SchemaProperty(AdvancedFormActions)
    arbitrary_datums = SchemaListProperty(ArbitraryDatum)
    schedule = SchemaProperty(FormSchedule, default=None)

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
        for action_tag, action_meta in actions.items():
            by_type[action_meta.get('type')].append(action_tag)

        for type, tag_list in by_type.items():
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
        return (
            self.uses_case_type(const.USERCASE_TYPE)
            or any(action for action in self.actions.load_update_cases
                   if action.auto_select and action.auto_select.mode == const.AUTO_SELECT_USERCASE)
        )

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
                format_key(*item) for item in action.case_properties.items())
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
            options = [(self.shadow_parent_form_id, gettext_lazy("Unknown, please change"))] + options
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


# backwards compatibility with suite-1.0.xml
FormBase.get_command_id = lambda self: id_strings.form_command(self)
FormBase.get_locale_id = lambda self: id_strings.form_locale(self)
