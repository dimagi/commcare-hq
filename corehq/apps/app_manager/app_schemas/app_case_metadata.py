from __future__ import absolute_import, unicode_literals

import datetime
import re

from django.utils.translation import ugettext_lazy as _

import six
from jsonobject.base import DefaultProperty

from dimagi.ext.jsonobject import (
    BooleanProperty,
    DictProperty,
    JsonObject,
    ListProperty,
    ObjectProperty,
    StringProperty,
)

from corehq.apps.app_manager.app_schemas.case_properties import (
    get_parent_type_map,
)
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.models import (
    AdvancedForm,
    AdvancedModule,
    Form,
    FormAction,
    FormActionCondition,
    Module,
)
from corehq.apps.app_manager.xform import VELLUM_TYPES
from corehq.apps.data_dictionary.util import get_case_property_description_dict
from corehq.util.timezones.conversions import PhoneTime
from corehq.util.timezones.utils import get_timezone_for_request


class AppCaseMetadataBuilder(object):
    def __init__(self, domain, app):
        self.domain = domain
        self.app = app
        self.meta = AppCaseMetadata()

    def case_metadata(self):
        self._build_case_relationships()
        self._add_module_contributions()
        self._add_form_contributions()
        self._add_case_property_descriptions()
        return self.meta

    def _build_case_relationships(self):
        case_relationships = get_parent_type_map(self.app)
        for case_type, relationships in case_relationships.items():
            self.meta.get_type(case_type).relationships = relationships

    def _add_module_contributions(self):
        for module in self.app.get_modules():
            if isinstance(module, (Module, AdvancedModule)):
                self._add_module_contribution(module)

    def _add_module_contribution(self, module):
        for column in module.case_details.long.columns:
            self.meta.add_property_detail('long', module.case_type, module.unique_id, column)
        for column in module.case_details.short.columns:
            self.meta.add_property_detail('short', module.case_type, module.unique_id, column)

    def _add_form_contributions(self):
        for module in self.app.get_modules():
            for form in module.get_forms():
                if isinstance(form, Form):
                    _FormCaseMetadataBuilder(self.meta, form).add_form_contributions()
                elif isinstance(form, AdvancedForm):
                    _AdvancedFormCaseMetadataBuilder(self.meta, form).add_form_contributions()

    def _add_case_property_descriptions(self):
        descriptions_dict = get_case_property_description_dict(self.domain)
        for type_ in self.meta.case_types:
            for prop in type_.properties:
                prop.description = descriptions_dict.get(type_.name, {}).get(prop.name, '')


class _BaseFormCaseMetadataBuilder(object):
    def __init__(self, meta, form):
        self.meta = meta
        self.form = form
        self.questions = {q['value']: FormQuestionResponse(q) for q in self.form.cached_get_questions()}

    def add_form_contributions(self):
        self._add_save_to_case_questions()

    def _add_save_to_case_questions(self):
        # The information for save to case questions comes directly from Vellum
        form_id = self.form.unique_id
        for property_info in self.form.case_references_data.get_save_references():
            if not property_info.case_type:
                # If there is no case type given by the user, we can't really
                # infer what this save to case question refers to
                continue

            for property_name in property_info.properties:
                question = FormQuestionResponse.wrap({
                    "label": property_info.path,
                    "tag": property_info.path,
                    "value": property_info.path,
                    "repeat": None,
                    "group": None,
                    "type": 'SaveToCase',
                    "relevant": None,
                    "required": None,
                    "comment": None,
                    "hashtagValue": property_info.path,
                })
                self.meta.add_property_save(property_info.case_type, property_name, form_id, question)

            type_meta = self.meta.get_type(property_info.case_type)
            if property_info.create:
                type_meta.add_opener(form_id, FormActionCondition(type='always'))
            if property_info.close:
                type_meta.add_closer(form_id, FormActionCondition(type='always'))

    def _add_property_save(self, case_type, name, question_path, condition=None):
        try:
            question = self.questions[question_path]
        except KeyError:
            message = "%s is not a valid question" % question_path
            self.meta.add_property_error(case_type, name, self.form.unique_id, message)
        else:
            self.meta.add_property_save(case_type, name, self.form.unique_id, question, condition)

    def _add_property_load(self, case_type, name, question_path):
        try:
            question = self.questions[question_path]
        except KeyError:
            message = "%s is not a valid question" % question_path
            self.meta.add_property_error(case_type, name, self.form.unique_id, message)
        else:
            self.meta.add_property_load(case_type, name, self.form.unique_id, question)


class _FormCaseMetadataBuilder(_BaseFormCaseMetadataBuilder):
    def __init__(self, meta, form):
        super(_FormCaseMetadataBuilder, self).__init__(meta, form)
        self.case_type = self.form.get_module().case_type

    def add_form_contributions(self):
        super(_FormCaseMetadataBuilder, self).add_form_contributions()
        self._add_form_actions()
        self._add_load_references()

    def _add_form_actions(self):
        for action_type, action in self.form.active_actions().items():
            if action_type == 'open_case':
                self._handle_open_case_action(action)

            if action_type == 'close_case':
                self._handle_close_case_action(action)

            if action_type in ('update_case', 'usercase_update'):
                self._handle_update_case_action(action_type, action)

            if action_type in ('case_preload', 'load_from_form', 'usercase_preload'):
                self._handle_load_action(action_type, action)

            if action_type == 'subcases':
                self._handle_subcase_actions(action)

    def _handle_open_case_action(self, action):
        type_meta = self.meta.get_type(self.case_type)
        type_meta.add_opener(self.form.unique_id, action.condition)
        self._add_property_save(self.case_type, 'name', action.name_path)

    def _handle_close_case_action(self, action):
        type_meta = self.meta.get_type(self.case_type)
        type_meta.add_closer(self.form.unique_id, action.condition)

    def _handle_update_case_action(self, action_type, action):
        case_type = USERCASE_TYPE if action_type == 'usercase_update' else self.case_type
        for name, question_path in FormAction.get_action_properties(action):
            self._add_property_save(case_type, name, question_path)

    def _handle_load_action(self, action_type, action):
        case_type = USERCASE_TYPE if action_type == 'usercase_update' else self.case_type
        for name, question_path in FormAction.get_action_properties(action):
            self._add_property_load(case_type, name, question_path)

    def _handle_subcase_actions(self, actions):
        active_actions = [a for a in actions if a.is_active()]
        for action in active_actions:
            sub_type_meta = self.meta.get_type(action.case_type)
            sub_type_meta.add_opener(self.form.unique_id, action.condition)
            if action.close_condition.is_active():
                sub_type_meta.add_closer(self.form.unique_id, action.close_condition)
            for name, question_path in FormAction.get_action_properties(action):
                self._add_property_save(action.case_type, name, question_path)

    def _add_load_references(self):
        for case_load_reference in self.form.case_references.get_load_references():
            for name in case_load_reference.properties:
                case_type, name = self._parse_case_type(name)
                name = re.sub("^grandparent/", "parent/parent/", name)
                self._add_property_load(case_type, name, case_load_reference.path)

    def _parse_case_type(self, full_name):
        if full_name.startswith("#case/"):
            return self.case_type, full_name.split("/", 1)[1]
        elif full_name.startswith("#user/"):
            return USERCASE_TYPE, full_name.split("/", 1)[1]
        else:
            return self.case_type, full_name


class _AdvancedFormCaseMetadataBuilder(_BaseFormCaseMetadataBuilder):
    def add_form_contributions(self):
        super(_AdvancedFormCaseMetadataBuilder, self).add_form_contributions()
        self._add_load_update_actions()
        self._add_open_actions()

    def _add_load_update_actions(self):
        for action in self.form.actions.load_update_cases:
            for name, question_path in action.case_properties.items():
                self._add_property_save(action.case_type, name, question_path)
            for question_path, name in action.preload.items():
                self._add_property_load(action.case_type, name, question_path)
            if action.close_condition.is_active():
                meta = self.meta.get_type(action.case_type)
                meta.add_closer(self.form.unique_id, action.close_condition)

    def _add_open_actions(self):
        for action in self.form.actions.open_cases:
            self._add_property_save(action.case_type, 'name', action.name_path, action.open_condition)
            for name, question_path in action.case_properties.items():
                self._add_property_save(action.case_type, name, question_path, action.open_condition)
            meta = self.meta.get_type(action.case_type)
            meta.add_opener(self.form.unique_id, action.open_condition)
            if action.close_condition.is_active():
                meta.add_closer(self.form.unique_id, action.close_condition)


class CaseMetaException(Exception):
    pass


class FormQuestionOption(JsonObject):
    label = StringProperty()
    value = StringProperty()


class FormQuestion(JsonObject):
    label = StringProperty()
    translations = DictProperty(exclude_if_none=True)
    tag = StringProperty()
    type = StringProperty(choices=list(VELLUM_TYPES))
    value = StringProperty()
    repeat = StringProperty()
    group = StringProperty()
    options = ListProperty(FormQuestionOption)
    calculate = StringProperty()
    relevant = StringProperty()
    required = BooleanProperty()
    comment = StringProperty()
    setvalue = StringProperty()

    @property
    def icon(self):
        try:
            return VELLUM_TYPES[self.type]['icon']
        except KeyError:
            return 'fa fa-question-circle'

    @property
    def relative_value(self):
        if self.group:
            prefix = self.group + '/'
            if self.value.startswith(prefix):
                return self.value[len(prefix):]
        return '/'.join(self.value.split('/')[2:])

    @property
    def option_values(self):
        return [o.value for o in self.options]

    @property
    def editable(self):
        if not self.type:
            return True
        vtype = VELLUM_TYPES[self.type]
        if 'editable' not in vtype:
            return False
        return vtype['editable']


class LoadSaveProperty(JsonObject):
    case_type = StringProperty()
    property = StringProperty()


class FormQuestionResponse(FormQuestion):
    response = DefaultProperty()
    children = ListProperty(lambda: FormQuestionResponse)

    def get_formatted_response(self):
        timezone = get_timezone_for_request()
        if self.type == 'DateTime' and timezone \
                and isinstance(self.response, datetime.datetime):
            return (PhoneTime(self.response, timezone).user_time(timezone)
                    .ui_string())
        else:
            return self.response


class ConditionalFormQuestionResponse(JsonObject):
    question = ObjectProperty(FormQuestionResponse)
    condition = ObjectProperty(FormActionCondition)


class QuestionList(JsonObject):
    questions = ListProperty(FormQuestionResponse)


class ConditionList(JsonObject):
    conditions = ListProperty(FormActionCondition)


class CaseFormMeta(JsonObject):
    form_id = StringProperty()
    load_questions = ListProperty(ConditionalFormQuestionResponse)
    save_questions = ListProperty(ConditionalFormQuestionResponse)
    errors = ListProperty(six.text_type)


class CaseDetailMeta(JsonObject):
    module_id = StringProperty()
    header = DictProperty()
    error = StringProperty()


class CaseProperty(JsonObject):
    case_type = StringProperty()
    name = StringProperty()
    forms = ListProperty(CaseFormMeta)
    short_details = ListProperty(CaseDetailMeta)
    long_details = ListProperty(CaseDetailMeta)
    has_errors = BooleanProperty()
    description = StringProperty()
    is_detail_calculation = BooleanProperty()

    def get_form(self, form_id):
        try:
            form = next(form for form in self.forms if form.form_id == form_id)
        except StopIteration:
            form = CaseFormMeta(form_id=form_id)
            self.forms.append(form)
        return form

    def add_load(self, form_id, question):
        form = self.get_form(form_id)
        form.load_questions.append(ConditionalFormQuestionResponse(
            question=question,
            condition=None
        ))

    def add_save(self, form_id, question, condition=None):
        form = self.get_form(form_id)
        form.save_questions.append(ConditionalFormQuestionResponse(
            question=question,
            condition=(condition if condition and condition.type == 'if' else None)
        ))

    def add_detail(self, type_, module_id, header, is_detail_calculation=False, error=None):
        self.is_detail_calculation = is_detail_calculation
        {
            "short": self.short_details,
            "long": self.long_details,
        }[type_].append(CaseDetailMeta(module_id=module_id, header=header, error=error))


class CaseTypeMeta(JsonObject):
    name = StringProperty(required=True)
    relationships = DictProperty()  # relationship name -> [child type 1, ...]
    properties = ListProperty(CaseProperty)  # property -> CaseProperty
    opened_by = DictProperty(ConditionList)  # form_ids -> [FormActionCondition, ...]
    closed_by = DictProperty(ConditionList)  # form_ids -> [FormActionCondition, ...]
    error = StringProperty()
    has_errors = BooleanProperty()

    # store where this case type gets loaded so that we can look it up more easily later
    load_properties = DictProperty()  # {"form_id": {"question_path": [CaseProperty, ...]}}
    save_properties = DictProperty()  # {"form_id": {"question_path": [CaseProperty, ...]}}

    @property
    def child_types(self):
        """ A list of all child types
        """
        return [child_type for relationship in self.relationships.values() for child_type in relationship]

    def get_property(self, name, allow_parent=False):
        if not allow_parent:
            assert '/' not in name, "Add parent properties to the correct case type"
        try:
            prop = next(prop for prop in self.properties if prop.name == name)
        except StopIteration:
            prop = CaseProperty(name=name, case_type=self.name)
            self.properties.append(prop)
        return prop

    def add_opener(self, form_id, condition):
        openers = self.opened_by.get(form_id, ConditionList())
        if condition.type == 'if':
            # only add optional conditions
            openers.conditions.append(condition)
        self.opened_by[form_id] = openers

    def add_closer(self, form_id, condition):
        closers = self.closed_by.get(form_id, ConditionList())
        if condition.type == 'if':
            # only add optional conditions
            closers.conditions.append(condition)
        self.closed_by[form_id] = closers

    def add_save(self, form_id, question_path, property_):
        if self.get_save_properties(form_id, question_path):
            self.save_properties[form_id][question_path].append(property_)
        else:
            try:
                self.save_properties[form_id].update({question_path: [property_]})
            except KeyError:
                self.save_properties[form_id] = {question_path: [property_]}

    def add_load(self, form_id, question_path, property_):
        if self.get_load_properties(form_id, question_path):
            self.load_properties[form_id][question_path].append(property_)
        else:
            try:
                self.load_properties[form_id].update({question_path: [property_]})
            except KeyError:
                self.load_properties[form_id] = {question_path: [property_]}

    def get_load_properties(self, form_id, path):
        """returns a list of properties which load into a particular form question
        """
        return self.load_properties.get(form_id, {}).get(path, [])

    def get_save_properties(self, form_id, path):
        """returns a list of properties which load into a particular form question
        """
        return self.save_properties.get(form_id, {}).get(path, [])


class AppCaseMetadata(JsonObject):
    case_types = ListProperty(CaseTypeMeta)  # case_type -> CaseTypeMeta

    def get_load_properties(self, form_id, path):
        """gets all case types with a list of properties which load into a form question
        """
        return [
            LoadSaveProperty(case_type=case_type.name, property=prop)
            for case_type in self.case_types
            for prop in case_type.get_load_properties(form_id, path)
        ]

    def get_save_properties(self, form_id, path):
        """gets all case types with a list of properties which are saved from a form question
        """
        return [
            LoadSaveProperty(case_type=case_type.name, property=prop)
            for case_type in self.case_types
            for prop in case_type.get_save_properties(form_id, path)
        ]

    def get_property_list(self, root_case_type, name):
        type_ = self.get_type(root_case_type)
        if '/' in name:
            # find the case property from the correct case type
            parent_rel, name = name.split('/', 1)
            parent_case_types = type_.relationships.get(parent_rel)
            if parent_case_types:
                parent_props = [
                    prop for parent_case_type in parent_case_types
                    for prop in self.get_property_list(parent_case_type, name)
                ]
                if parent_props:
                    return parent_props
            else:
                params = {'case_type': root_case_type, 'relationship': parent_rel}
                raise CaseMetaException(_(
                    "Case type '%(case_type)s' has no '%(relationship)s' "
                    "relationship to any other case type.") % params)

        return [type_.get_property(name)]

    def add_property_load(self, root_case_type, name, form_id, question):
        try:
            props = self.get_property_list(root_case_type, name)
        except CaseMetaException as e:
            props = [self.add_property_error(root_case_type, name, form_id, str(e))]

        for prop in props:
            self.get_type(prop.case_type).add_load(form_id, question.value, prop.name)
            prop.add_load(form_id, question)

    def add_property_save(self, root_case_type, name, form_id, question, condition=None):
        try:
            props = self.get_property_list(root_case_type, name)
        except CaseMetaException as e:
            props = [self.add_property_error(root_case_type, name, form_id, str(e))]

        for prop in props:
            self.get_type(prop.case_type).add_save(form_id, question.value, prop.name)
            prop.add_save(form_id, question, condition)

    def add_property_error(self, case_type, case_property, form_id, message):
        prop = self.get_error_property(case_type, case_property)
        prop.has_errors = True
        if form_id is not None:
            form = prop.get_form(form_id)
            form.errors.append(message)
        return prop

    def add_property_detail(self, detail_type, root_case_type, module_id, column):
        field = column.field
        if field == '#owner_name':
            return None

        parts = field.split('/')
        if parts and parts[0] == 'user':
            root_case_type = USERCASE_TYPE
            field = field.split('user/')[1]

        error = None
        try:
            if column.useXpathExpression:
                props = [self.get_type(root_case_type).get_property(field, allow_parent=True)]
            else:
                props = self.get_property_list(root_case_type, field)
        except CaseMetaException as e:
            props = [self.add_property_error(root_case_type, field, form_id=None, message=None)]
            error = six.text_type(e)
        for prop in props:
            prop.add_detail(detail_type, module_id, column.header, column.useXpathExpression, error)

    def get_error_property(self, case_type, name):
        type_ = self.get_type(case_type)
        type_.has_errors = True
        return type_.get_property(name, allow_parent=True)

    def get_type(self, name):
        if not name:
            return CaseTypeMeta(name='')

        try:
            type_ = next(type_ for type_ in self.case_types if type_.name == name)
        except StopIteration:
            type_ = CaseTypeMeta(name=name)
            self.case_types.append(type_)

        return type_
