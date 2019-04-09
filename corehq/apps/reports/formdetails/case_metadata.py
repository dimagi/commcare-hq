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
    CaseMetaException,
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
                if not isinstance(form, (Form, AdvancedForm)):
                    continue

                questions = {q['value']: FormQuestionResponse(q) for q in form.cached_get_questions()}
                self._add_save_to_case_questions(form)
                if isinstance(form, Form):
                    self._add_regular_form_contribution(form, questions)
                elif isinstance(form, AdvancedForm):
                    self._add_advanced_form_contribution(form, questions)

    def _add_regular_form_contribution(self, form, questions):
        module_case_type = form.get_module().case_type
        type_meta = self.meta.get_type(module_case_type)
        for type_, action in form.active_actions().items():
            if type_ == 'open_case':
                type_meta.add_opener(form.unique_id, action.condition)
                self.add_property_save(
                    form,
                    module_case_type,
                    'name',
                    questions,
                    action.name_path
                )
            if type_ == 'close_case':
                type_meta.add_closer(form.unique_id, action.condition)
            if type_ == 'update_case' or type_ == 'usercase_update':
                for name, question_path in FormAction.get_action_properties(action):
                    self.add_property_save(
                        form,
                        USERCASE_TYPE if type_ == 'usercase_update' else module_case_type,
                        name,
                        questions,
                        question_path
                    )
            if type_ == 'case_preload' or type_ == 'load_from_form' or type_ == 'usercase_preload':
                for name, question_path in FormAction.get_action_properties(action):
                    self.add_property_load(
                        form,
                        USERCASE_TYPE if type_ == 'usercase_preload' else module_case_type,
                        name,
                        questions,
                        question_path
                    )
            if type_ == 'subcases':
                for act in action:
                    if act.is_active():
                        sub_type_meta = self.meta.get_type(act.case_type)
                        sub_type_meta.add_opener(form.unique_id, act.condition)
                        if act.close_condition.is_active():
                            sub_type_meta.add_closer(form.unique_id, act.close_condition)
                        for name, question_path in FormAction.get_action_properties(act):
                            self.add_property_save(
                                form,
                                act.case_type,
                                name,
                                questions,
                                question_path
                            )

        for case_load_reference in form.case_references.get_load_references():
            for name in case_load_reference.properties:
                case_type, name = _parse_case_type(name, module_case_type)
                name = re.sub("^grandparent/", "parent/parent/", name)
                self.add_property_load(
                    form,
                    case_type,
                    name,
                    questions,
                    case_load_reference.path
                )

    def _add_advanced_form_contribution(self, form, questions):
        for action in form.actions.load_update_cases:
            for name, question_path in action.case_properties.items():
                self.add_property_save(
                    form,
                    action.case_type,
                    name,
                    questions,
                    question_path
                )
            for question_path, name in action.preload.items():
                self.add_property_load(
                    form,
                    action.case_type,
                    name,
                    questions,
                    question_path
                )
            if action.close_condition.is_active():
                meta = self.meta.get_type(action.case_type)
                meta.add_closer(form.unique_id, action.close_condition)

        for action in form.actions.open_cases:
            self.add_property_save(
                form,
                action.case_type,
                'name',
                questions,
                action.name_path,
                action.open_condition
            )
            for name, question_path in action.case_properties.items():
                self.add_property_save(
                    form,
                    action.case_type,
                    name,
                    questions,
                    question_path,
                    action.open_condition
                )
            meta = self.meta.get_type(action.case_type)
            meta.add_opener(form.unique_id, action.open_condition)
            if action.close_condition.is_active():
                meta.add_closer(form.unique_id, action.close_condition)

    def _add_save_to_case_questions(self, form):
        # The information for save to case questions comes directly from Vellum
        for property_info in form.case_references_data.get_save_references():
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
                self.meta.add_property_save(property_info.case_type,
                                            property_name, form.unique_id,
                                            question)

            type_meta = self.meta.get_type(property_info.case_type)
            if property_info.create:
                type_meta.add_opener(form.unique_id, FormActionCondition(type='always'))
            if property_info.close:
                type_meta.add_closer(form.unique_id, FormActionCondition(type='always'))

    def add_property_save(self, form, case_type, name,
                          questions, question_path, condition=None):
        if question_path in questions:
            self.meta.add_property_save(
                case_type,
                name,
                form.unique_id,
                questions[question_path],
                condition
            )
        else:
            self.meta.add_property_error(
                case_type,
                name,
                form.unique_id,
                "%s is not a valid question" % question_path
            )

    def add_property_load(self, form, case_type, name,
                          questions, question_path):
        if question_path in questions:
            self.meta.add_property_load(
                case_type,
                name,
                form.unique_id,
                questions[question_path]
            )
        else:
            self.meta.add_property_error(
                case_type,
                name,
                form.unique_id,
                "%s is not a valid question" % question_path
            )

    def _add_case_property_descriptions(self):
        descriptions_dict = get_case_property_description_dict(self.domain)
        for type_ in self.meta.case_types:
            for prop in type_.properties:
                prop.description = descriptions_dict.get(type_.name, {}).get(prop.name, '')


def _parse_case_type(full_name, module_case_type):
    if full_name.startswith("#case/"):
        return module_case_type, full_name.split("/", 1)[1]
    elif full_name.startswith("#user/"):
        return USERCASE_TYPE, full_name.split("/", 1)[1]
    else:
        return module_case_type, full_name
