from __future__ import absolute_import, unicode_literals

import re

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
from corehq.apps.data_dictionary.util import get_case_property_description_dict
from corehq.apps.reports.formdetails.readable import (
    AppCaseMetadata,
    FormQuestionResponse,
)


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
                    _RegularFormCaseMetadataBuilder(self.meta, form).add_form_contributions()
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


class _RegularFormCaseMetadataBuilder(_BaseFormCaseMetadataBuilder):
    def __init__(self, meta, form):
        super(_RegularFormCaseMetadataBuilder, self).__init__(meta, form)
        self.case_type = self.form.get_module().case_type

    def add_form_contributions(self):
        super(_RegularFormCaseMetadataBuilder, self).add_form_contributions()
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
                case_type, name = self._parse_case_type(name, self.case_type)
                name = re.sub("^grandparent/", "parent/parent/", name)
                self._add_property_load(case_type, name, case_load_reference.path)

    @staticmethod
    def _parse_case_type(full_name, module_case_type):
        if full_name.startswith("#case/"):
            return module_case_type, full_name.split("/", 1)[1]
        elif full_name.startswith("#user/"):
            return USERCASE_TYPE, full_name.split("/", 1)[1]
        else:
            return module_case_type, full_name


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
