from __future__ import absolute_import, unicode_literals

import re
from collections import defaultdict

import six
from deepdiff import DeepDiff

from corehq.apps.app_manager.app_schemas.app_case_metadata import (
    AppCaseMetadata,
    FormQuestionResponse,
)
from corehq.apps.app_manager.exceptions import XFormException

REMOVED = 'removed'
ADDED = 'added'
CHANGED = 'changed'

INTERESTING_ATTRIBUTES = ('name', 'label', 'constraint', 'calculate', 'comment', 'required', 'setvalue', 'relevant')


class _AppSummaryFormDataGenerator(object):
    def __init__(self, domain, app, include_shadow_forms=True):
        self.domain = domain
        self.app = app
        self.include_shadow_forms = include_shadow_forms

        self.errors = []

        self._seen_save_to_case = defaultdict(list)
        try:
            self._case_meta = self.app.get_case_metadata()
        except XFormException:
            self._case_meta = AppCaseMetadata()

    def generate(self):
        return [self._compile_module(module) for module in self.app.get_modules()], self.errors

    def _compile_module(self, module):
        return {
            'id': module.unique_id,
            'name': module.name,
            'short_comment': module.short_comment,
            'module_type': module.module_type,
            'is_surveys': module.is_surveys,
            'module_filter': module.module_filter,
            'forms': [self._compile_form(form) for form in self._get_pertinent_forms(module)],
        }

    def _get_pertinent_forms(self, module):
        from corehq.apps.app_manager.models import ShadowForm
        if not self.include_shadow_forms:
            return [form for form in module.get_forms() if not isinstance(form, ShadowForm)]
        return module.get_forms()

    def _compile_form(self, form):
        form_meta = {
            'id': form.unique_id,
            'name': form.name,
            'short_comment': form.short_comment,
            'action_type': form.get_action_type(),
            'form_filter': form.form_filter,
        }
        try:
            form_meta['questions'] = [
                question
                for raw_question in form.get_questions(self.app.langs, include_triggers=True,
                                                       include_groups=True, include_translations=True)
                for question in self._get_question(form.unique_id, raw_question)
            ]
        except XFormException as exception:
            form_meta['questions'] = []
            form_meta['error'] = {
                'details': six.text_type(exception),
            }
            self.errors.append(form_meta)
        return form_meta

    def _get_question(self, form_unique_id, question):
        if self._needs_save_to_case_root_node(question, form_unique_id):
            yield self._save_to_case_root_node(form_unique_id, question)
        yield self._serialized_question(form_unique_id, question)

    def _needs_save_to_case_root_node(self, question, form_unique_id):
        return (
            self._is_save_to_case(question)
            and self._save_to_case_root_path(question) not in self._seen_save_to_case[form_unique_id]
        )

    @staticmethod
    def _is_save_to_case(question):
        return '/case/' in question['value']

    @staticmethod
    def _save_to_case_root_path(question):
        return question['value'].split('/case/')[0]

    def _save_to_case_root_node(self, form_unique_id, question):
        """Add an extra node with the root path of the save to case to attach case properties to
        """
        question_path = self._save_to_case_root_path(question)
        response = FormQuestionResponse({
            "label": question_path,
            "tag": question_path,
            "value": question_path,
            "repeat": question['repeat'],
            "group": question['group'],
            "type": 'SaveToCase',
            "hashtagValue": question['hashtagValue'],
            "relevant": None,
            "required": False,
            "comment": None,
            "constraint": None,
        }).to_json()
        response['load_properties'] = self._case_meta.get_load_properties(form_unique_id, question_path)
        response['save_properties'] = self._case_meta.get_save_properties(form_unique_id, question_path)
        self._seen_save_to_case[form_unique_id].append(question_path)
        return response

    def _serialized_question(self, form_unique_id, question):
        response = FormQuestionResponse(question).to_json()
        response['load_properties'] = self._case_meta.get_load_properties(form_unique_id, question['value'])
        response['save_properties'] = self._case_meta.get_save_properties(form_unique_id, question['value'])
        if self._is_save_to_case(question):
            response['type'] = 'SaveToCase'
        return response


def get_app_summary_formdata(domain, app, include_shadow_forms=True):
    """Returns formdata formatted for the app summary
    """
    return _AppSummaryFormDataGenerator(domain, app, include_shadow_forms).generate()


class AppDiffGenerator(object):
    def __init__(self, app1, app2):
        self.first = get_app_summary_formdata(app1.domain, app1)[0]
        self.second = get_app_summary_formdata(app2.domain, app2)[0]

        self._populate_id_caches()
        self._mark_removed_items()
        self._mark_added_items()

    def _populate_id_caches(self):
        self._first_ids = set()
        self._first_questions_by_id = defaultdict(dict)
        self._second_ids = set()
        self._second_questions_by_id = defaultdict(dict)

        for module in self.first:
            self._first_ids.add(module['id'])
            for form in module['forms']:
                self._first_ids.add(form['id'])
                for question in form['questions']:
                    self._first_questions_by_id[form['id']][question['value']] = question

        for module in self.second:
            self._second_ids.add(module['id'])
            for form in module['forms']:
                self._second_ids.add(form['id'])
                for question in form['questions']:
                    self._second_questions_by_id[form['id']][question['value']] = question

    def _mark_removed_items(self):
        for module in self.first:
            if module['id'] not in self._second_ids:
                module['diff_state'] = REMOVED
            else:
                self._mark_removed_forms(module['forms'])

    def _mark_removed_forms(self, forms):
        for form in forms:
            if form['id'] not in self._second_ids:
                form['diff_state'] = REMOVED
            else:
                self._mark_removed_questions(form['id'], form.get('questions', []))

    def _mark_removed_questions(self, form_id, questions):
        for question in questions:
            if question['value'] not in self._second_questions_by_id[form_id]:
                question['diff_state'] = REMOVED

    def _mark_added_items(self):
        for module in self.second:
            if module['id'] not in self._first_ids:
                module['diff_state'] = ADDED
            else:
                self._mark_added_forms(module['forms'])

    def _mark_added_forms(self, forms):
        for form in forms:
            if form['id'] not in self._first_ids:
                form['diff_state'] = ADDED
            else:
                self._mark_added_questions(form['id'], form['questions'])

    def _mark_added_questions(self, form_id, questions):
        for second_question in questions:
            question_path = second_question['value']
            if question_path not in self._first_questions_by_id[form_id]:
                second_question['diff_state'] = ADDED
            else:
                first_question = self._first_questions_by_id[form_id][question_path]
                self._mark_changed_questions(first_question, second_question)

    def _mark_changed_questions(self, first_question, second_question):
        for attribute in INTERESTING_ATTRIBUTES:
            attribute_changed = first_question.get(attribute) != second_question.get(attribute)
            attribute_added = not first_question.get(attribute) and second_question.get(attribute)
            if (attribute_changed or attribute_added):
                first_question['diff_state'] = CHANGED
                second_question['diff_state'] = CHANGED


def get_app_diff(app1, app2):
    return AppDiffGenerator(app1, app2)
