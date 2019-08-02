from __future__ import absolute_import, unicode_literals

from collections import OrderedDict, defaultdict

import six
from jsonobject import (
    BooleanProperty,
    DictProperty,
    JsonObject,
    ListProperty,
    ObjectProperty,
    StringProperty,
)

from corehq.apps.app_manager.app_schemas.app_case_metadata import (
    AppCaseMetadata,
    FormQuestionResponse,
    LoadSaveProperty,
)
from corehq.apps.app_manager.exceptions import XFormException

REMOVED = 'removed'
ADDED = 'added'
CHANGED = 'changed'

DIFF_STATES = (REMOVED, ADDED, CHANGED)

QUESTION_ATTRIBUTES = (
    'label', 'type', 'value', 'options', 'calculate', 'relevant',
    'required', 'comment', 'setvalue', 'constraint',
    'load_properties', 'save_properties'
)

FORM_ATTRIBUTES = (
    'name', 'short_comment', 'form_filter'
)

MODULE_ATTRIBUTES = (
    'name', 'short_comment', 'module_filter'
)


class _Change(JsonObject):
    action = StringProperty(choices=DIFF_STATES)
    old_value = StringProperty()
    new_value = StringProperty()

class _TranslationChange(_Change):
    old_value = DictProperty()
    new_value = DictProperty()

class _QuestionDiff(JsonObject):
    question = ObjectProperty(_Change)
    label = ObjectProperty(_Change)
    type = ObjectProperty(_Change)
    value = ObjectProperty(_Change)
    calculate = ObjectProperty(_Change)
    relevant = ObjectProperty(_Change)
    required = ObjectProperty(_Change)
    comment = ObjectProperty(_Change)
    setvalue = ObjectProperty(_Change)
    constraint = ObjectProperty(_Change)
    options = DictProperty()    # {option: _Change}
    load_properties = DictProperty()  # {case_type: {property: _Change}}
    save_properties = DictProperty()  # {case_type: {property: _Change}}


class _FormDiff(JsonObject):
    form = ObjectProperty(_Change)
    name = ObjectProperty(_Change)
    short_comment = ObjectProperty(_Change)
    form_filter = ObjectProperty(_Change)
    contains_changes = BooleanProperty(default=False)


class _ModuleDiff(JsonObject):
    module = ObjectProperty(_Change)
    name = ObjectProperty(_Change)
    short_comment = ObjectProperty(_Change)
    module_filter = ObjectProperty(_Change)
    contains_changes = BooleanProperty(default=False)


class _FormMetadataQuestion(FormQuestionResponse):
    form_id = StringProperty()
    load_properties = ListProperty(LoadSaveProperty)
    save_properties = ListProperty(LoadSaveProperty)
    changes = ObjectProperty(_QuestionDiff)


class _FormMetadata(JsonObject):
    unique_id = StringProperty()
    name = DictProperty()
    short_comment = StringProperty()
    action_type = StringProperty()
    form_filter = StringProperty()
    questions = ListProperty(_FormMetadataQuestion)
    error = DictProperty()
    changes = ObjectProperty(_FormDiff)


class _ModuleMetadata(JsonObject):
    unique_id = StringProperty()
    name = DictProperty()
    short_comment = StringProperty()
    module_type = StringProperty()
    is_surveys = BooleanProperty()
    module_filter = StringProperty()
    forms = ListProperty(_FormMetadata)
    changes = ObjectProperty(_ModuleDiff)


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
        return _ModuleMetadata(**{
            'unique_id': module.unique_id,
            'name': module.name,
            'short_comment': module.short_comment,
            'module_type': module.module_type,
            'is_surveys': module.is_surveys,
            'module_filter': module.module_filter,
            'forms': [self._compile_form(form) for form in self._get_pertinent_forms(module)],
        })

    def _get_pertinent_forms(self, module):
        from corehq.apps.app_manager.models import ShadowForm
        if not self.include_shadow_forms:
            return [form for form in module.get_forms() if not isinstance(form, ShadowForm)]
        return module.get_forms()

    def _compile_form(self, form):
        form_meta = _FormMetadata(**{
            'unique_id': form.unique_id,
            'name': form.name,
            'short_comment': form.short_comment,
            'action_type': form.get_action_type(),
            'form_filter': form.form_filter,
        })
        try:
            form_meta.questions = self._sort_questions_by_group(form)
        except XFormException as exception:
            form_meta.error = {
                'details': six.text_type(exception),
            }
            self.errors.append(form_meta)
        return form_meta

    def _sort_questions_by_group(self, form):
        questions_by_path = OrderedDict(
            (question.value, question)
            for raw_question in form.get_questions(self.app.langs, include_triggers=True,
                                                   include_groups=True, include_translations=True)
            for question in self._get_question(form.unique_id, raw_question)
        )
        for path, question in six.iteritems(questions_by_path):
            parent = question.group or question.repeat
            if parent:
                questions_by_path[parent].children.append(question)

        return [question for question in six.itervalues(questions_by_path)
                if not question.group and not question.repeat]

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
        response = _FormMetadataQuestion(**{
            "form_id": form_unique_id,
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
            "load_properties": self._case_meta.get_load_properties(form_unique_id, question_path),
            "save_properties": self._case_meta.get_save_properties(form_unique_id, question_path)
        })
        self._seen_save_to_case[form_unique_id].append(question_path)
        return response

    def _serialized_question(self, form_unique_id, question):
        response = _FormMetadataQuestion(question)
        response.form_id = form_unique_id
        response.load_properties = self._case_meta.get_load_properties(form_unique_id, question['value'])
        response.save_properties = self._case_meta.get_save_properties(form_unique_id, question['value'])
        if self._is_save_to_case(question):
            response.type = 'SaveToCase'
        return response


def get_app_summary_formdata(domain, app, include_shadow_forms=True):
    """Returns formdata formatted for the app summary
    """
    return _AppSummaryFormDataGenerator(domain, app, include_shadow_forms).generate()


class _AppDiffGenerator(object):
    def __init__(self, app1, app2):
        self.first = get_app_summary_formdata(app1.domain, app1)[0]
        self.second = get_app_summary_formdata(app2.domain, app2)[0]

        self._first_by_id = {}
        self._first_questions_by_form_id = defaultdict(dict)
        self._second_by_id = {}
        self._second_questions_by_form_id = defaultdict(dict)
        self._populate_id_caches()

        self._mark_removed_items()
        self._mark_retained_items()

    def _populate_id_caches(self):
        def add_question_to_id_cache(id_cache, form_id, question_path, question):
            for child in question.children:
                add_question_to_id_cache(id_cache, form_id, child['value'], child)
            id_cache[form_id][question_path] = question

        for module in self.first:
            self._first_by_id[module['unique_id']] = module
            for form in module['forms']:
                self._first_by_id[form['unique_id']] = form
                for question in form['questions']:
                    add_question_to_id_cache(self._first_questions_by_form_id,
                                             form['unique_id'], question['value'], question)

        for module in self.second:
            self._second_by_id[module['unique_id']] = module
            for form in module['forms']:
                self._second_by_id[form['unique_id']] = form
                for question in form['questions']:
                    add_question_to_id_cache(self._second_questions_by_form_id,
                                             form['unique_id'], question['value'], question)

    def _mark_removed_items(self):
        """Finds all removed modules, forms, and questions from the second app
        """
        for module in self.first:
            if module['unique_id'] not in self._second_by_id:
                self._mark_item_removed(module, 'module')
                continue

            for form in module['forms']:
                if form['unique_id'] not in self._second_by_id:
                    self._mark_item_removed(form, 'form')
                    continue

                self._mark_removed_questions(form['unique_id'], form['questions'])

    def _mark_removed_questions(self, unique_id, questions):
        for question in questions:
            self._mark_removed_questions(unique_id, question.children)
            if question.value not in self._second_questions_by_form_id[unique_id]:
                self._mark_item_removed(question, 'question')

    def _mark_retained_items(self):
        """Looks through each module and form that was not removed in the second app
        and marks changes and additions

        """
        for second_module in self.second:
            try:
                first_module = self._first_by_id[second_module['unique_id']]
                for attribute in MODULE_ATTRIBUTES:
                    self._mark_attribute(first_module, second_module, attribute)
                self._mark_forms(second_module['forms'])
            except KeyError:
                self._mark_item_added(second_module, 'module')

    def _mark_attribute(self, first_item, second_item, attribute):
        translation_changed = (self._is_translatable_property(first_item[attribute], second_item[attribute])
                               and set(second_item[attribute].items()) - set(first_item[attribute].items()))
        attribute_changed = first_item[attribute] != second_item[attribute]
        attribute_added = second_item[attribute] and not first_item[attribute]
        attribute_removed = first_item[attribute] and not second_item[attribute]
        if attribute_changed or translation_changed:
            self._mark_item_changed(first_item, second_item, attribute)
        if attribute_added:
            self._mark_item_added(second_item, attribute)
        if attribute_removed:
            self._mark_item_removed(first_item, attribute)

    @staticmethod
    def _is_translatable_property(first_property, second_property):
        return (isinstance(first_property, dict) and isinstance(second_property, dict))

    def _mark_forms(self, second_forms):
        for second_form in second_forms:
            try:
                first_form = self._first_by_id[second_form['unique_id']]
                for attribute in FORM_ATTRIBUTES:
                    self._mark_attribute(first_form, second_form, attribute)
                self._mark_questions(second_form['unique_id'], second_form['questions'])
            except KeyError:
                self._mark_item_added(second_form, 'form')

    def _mark_questions(self, form_id, second_questions):
        for second_question in second_questions:
            self._mark_questions(form_id, second_question.children)
            try:
                question_path = second_question['value']
                first_question = self._first_questions_by_form_id[form_id][question_path]
                self._mark_question_attributes(first_question, second_question)
            except KeyError:
                self._mark_item_added(second_question, 'question')

    def _mark_question_attributes(self, first_question, second_question):
        for attribute in QUESTION_ATTRIBUTES:
            if attribute == 'options':
                self._mark_options(first_question, second_question)
            elif attribute in ('save_properties', 'load_properties'):
                self._mark_case_properties(first_question, second_question, attribute)
            else:
                self._mark_attribute(first_question, second_question, attribute)

    def _mark_options(self, first_question, second_question):
        first_option_values = {option.value for option in first_question.options}
        second_option_values = {option.value for option in second_question.options}

        removed_options = first_option_values - second_option_values
        added_options = second_option_values - first_option_values

        potentially_changed_options = first_option_values & second_option_values
        first_options_by_value = {option.value: option.label for option in first_question.options}
        second_options_by_value = {option.value: option.label for option in second_question.options}
        changed_options = [
            option for option in potentially_changed_options
            if first_options_by_value[option] != second_options_by_value[option]
        ]

        for removed_option in removed_options:
            first_question.changes['options'][removed_option] = _Change(type=REMOVED).to_json()

        for added_option in added_options:
            second_question.changes['options'][added_option] = _Change(type=ADDED).to_json()

        for changed_option in changed_options:
            first_question.changes['options'][changed_option] = _Change(type=CHANGED).to_json()
            second_question.changes['options'][changed_option] = _Change(type=CHANGED).to_json()

        if removed_options or added_options or changed_options:
            self._set_contains_changes(first_question)
            self._set_contains_changes(second_question)

    def _mark_case_properties(self, first_question, second_question, attribute):
        first_props = {(prop.case_type, prop.property) for prop in first_question[attribute]}
        second_props = {(prop.case_type, prop.property) for prop in second_question[attribute]}
        removed_properties = first_props - second_props
        added_properties = second_props - first_props

        for removed_property in removed_properties:
            first_question.changes[attribute][removed_property[0]] = {removed_property[1]: _Change(type=REMOVED).to_json()}
        for added_property in added_properties:
            second_question.changes[attribute][added_property[0]] = {added_property[1]: _Change(type=ADDED).to_json()}

        if removed_properties or added_properties:
            self._set_contains_changes(first_question)
            self._set_contains_changes(second_question)

    def _mark_item_removed(self, item, key):
        self._set_contains_changes(item)
        try:
            old_value = item[key]
        except KeyError:
            old_value = None
        item.changes[key] = _Change(type=REMOVED, old_value=old_value)

    def _mark_item_added(self, item, key):
        self._set_contains_changes(item)
        try:
            new_value = item[key]
        except KeyError:
            new_value = None
        item.changes[key] = _Change(type=ADDED, new_value=new_value)

    def _mark_item_changed(self, first_item, second_item, key):
        self._set_contains_changes(first_item)
        self._set_contains_changes(second_item)
        if self._is_translatable_property(first_item[key], second_item[key]):
            change_class = _TranslationChange
        else:
            change_class = _Change
        change = change_class(type=CHANGED, old_value=first_item[key], new_value=second_item[key])
        first_item.changes[key] = change
        second_item.changes[key] = change

    def _set_contains_changes(self, item):
        """For forms and modules, set contains_changes to True
        For questions, set the form's contains_changes attribute to True

        This is used for the "View Changed Items" filter in the UI
        """
        try:
            for form in self._get_form_ancestors(item):
                form.changes.contains_changes = True
            item.changes.contains_changes = True
        except AttributeError:
            pass

    def _get_form_ancestors(self, question):
        """Returns forms from both apps with the same form_id.
        If something other than a question is passed in, it will be ignored

        """
        ancestors = []
        for tree in [self._first_by_id, self._second_by_id]:
            try:
                form_id = question['form_id']
                ancestors.append(tree[form_id])
            except KeyError:
                continue
        return ancestors


def get_app_diff(app1, app2):
    diff = _AppDiffGenerator(app1, app2)
    return diff.first, diff.second
