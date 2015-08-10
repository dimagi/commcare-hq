from pydoc import html
from django.http import Http404
from django.utils.safestring import mark_safe
from corehq.util.timezones.conversions import PhoneTime
from corehq.util.timezones.utils import get_timezone_for_request
from dimagi.ext.jsonobject import *
from jsonobject.base import DefaultProperty
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import Application, FormActionCondition
from corehq.apps.app_manager.xform import VELLUM_TYPES
from corehq.apps.reports.formdetails.exceptions import QuestionListNotFound
from django.utils.translation import ugettext_lazy as _


class CaseMetaException(Exception):
    pass


class FormQuestionOption(JsonObject):
    label = StringProperty()
    value = StringProperty()


class FormQuestion(JsonObject):
    label = StringProperty()
    translations = DictProperty(exclude_if_none=True)
    tag = StringProperty()
    type = StringProperty(choices=VELLUM_TYPES.keys())
    value = StringProperty()
    repeat = StringProperty()
    group = StringProperty()
    options = ListProperty(FormQuestionOption, exclude_if_none=True)
    calculate = StringProperty()
    relevant = StringProperty()
    required = BooleanProperty()

    @property
    def icon(self):
        try:
            return VELLUM_TYPES[self.type]['icon']
        except KeyError:
            return 'icon-question-sign'

    @property
    def relative_value(self):
        if self.group:
            prefix = self.group + '/'
            if self.value.startswith(prefix):
                return self.value[len(prefix):]
        return '/'.join(self.value.split('/')[2:])


class FormQuestionResponse(FormQuestion):
    response = DefaultProperty()
    children = ListProperty(lambda: FormQuestionResponse, exclude_if_none=True)

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
    errors = ListProperty(unicode)


class CaseProperty(JsonObject):
    name = StringProperty()
    forms = ListProperty(CaseFormMeta)
    has_errors = BooleanProperty()

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


class CaseTypeMeta(JsonObject):
    name = StringProperty(required=True)
    relationships = DictProperty()  # relationship name -> case type
    properties = ListProperty(CaseProperty)  # property -> CaseProperty
    opened_by = DictProperty(ConditionList)  # form_ids -> [FormActionCondition, ...]
    closed_by = DictProperty(ConditionList)  # form_ids -> [FormActionCondition, ...]
    error = StringProperty()
    has_errors = BooleanProperty()

    def get_property(self, name, allow_parent=False):
        if not allow_parent:
            assert '/' not in name, "Add parent properties to the correct case type"
        try:
            prop = next(prop for prop in self.properties if prop.name == name)
        except StopIteration:
            prop = CaseProperty(name=name)
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


class AppCaseMetadata(JsonObject):
    case_types = ListProperty(CaseTypeMeta)  # case_type -> CaseTypeMeta
    type_hierarchy = DictProperty()  # case_type -> {child_case -> {}}

    def get_property(self, root_case_type, name):
        type_ = self.get_type(root_case_type)
        if '/' in name:
            # find the case property from the correct case type
            parent_rel, name = name.split('/', 1)
            parent_case_type = type_.relationships.get(parent_rel)
            if parent_case_type:
                return self.get_property(parent_case_type, name)
            else:
                params = {'case_type': root_case_type, 'relationship': parent_rel}
                raise CaseMetaException(_(
                    "Case type '%(case_type)s' has no '%(relationship)s' "
                    "relationship to any other case type.") % params)

        return type_.get_property(name)

    def add_property_load(self, root_case_type, name, form_id, question):
        try:
            prop = self.get_property(root_case_type, name)
        except CaseMetaException as e:
            prop = self.add_property_error(root_case_type, name, form_id, str(e))

        prop.add_load(form_id, question)

    def add_property_save(self, root_case_type, name, form_id, question, condition=None):
        try:
            prop = self.get_property(root_case_type, name)
        except CaseMetaException as e:
            prop = self.add_property_error(root_case_type, name, form_id, str(e))

        prop.add_save(form_id, question, condition)

    def add_property_error(self, case_type, case_property, form_id, message):
        prop = self.get_error_property(case_type, case_property)
        prop.has_errors = True
        form = prop.get_form(form_id)
        form.errors.append(message)
        return prop

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


SYSTEM_FIELD_NAMES = (
    "drugs_prescribed", "case", "meta", "clinic_ids", "drug_drill_down", "tmp",
    "info_hack_done"
)


def form_key_filter(key):
    if key in SYSTEM_FIELD_NAMES:
        return False

    if key.startswith(('#', '@', '_')):
        return False

    return True


def get_questions(domain, app_id, xmlns):
    if not app_id:
        raise QuestionListNotFound(
            _("This form is not associated with an app")
        )
    try:
        app = get_app(domain, app_id)
    except Http404:
        raise QuestionListNotFound(
            _("No app could be found")
        )
    if not isinstance(app, Application):
        raise QuestionListNotFound(
            _("Remote apps are not supported")
        )

    form = app.get_form_by_xmlns(xmlns)
    if not form:
        if xmlns == 'http://code.javarosa.org/devicereport':
            raise QuestionListNotFound(
                _("This is a Device Report")
            )
        else:
            raise QuestionListNotFound(
                _("We could not find the question list "
                  "associated with this form")
            )
    # Search for 'READABLE FORMS TEST' for more info
    # to bootstrap a test and have it print out your form xml
    # uncomment this line. Ghetto but it works.
    # print form.wrapped_xform().render()
    return get_questions_from_xform_node(form.wrapped_xform(), app.langs)


def get_questions_from_xform_node(xform, langs):
    questions = xform.get_questions(
        langs, include_triggers=True, include_groups=True)
    return [FormQuestionResponse(q) for q in questions]


def get_questions_for_submission(xform):
    app_id = xform.build_id or xform.app_id
    domain = xform.domain
    xmlns = xform.xmlns

    try:
        questions = get_questions(domain, app_id, xmlns)
        questions_error = None
    except QuestionListNotFound as e:
        questions = []
        questions_error = e
    return questions, questions_error


def get_readable_data_for_submission(xform):
    questions, questions_error = get_questions_for_submission(xform)
    return get_readable_form_data(
        xform.form,
        questions,
        process_label=_html_interpolate_output_refs
    ), questions_error


def get_readable_form_data(xform_data, questions, process_label=None):
    return zip_form_data_and_questions(
        strip_form_data(xform_data),
        questions_in_hierarchy(questions),
        path_context='/%s/' % xform_data.get('#type', 'data'),
        process_label=process_label,
    )


def strip_form_data(data):
    data = data.copy()
    # remove all case, meta, attribute nodes from the top level
    for key in data.keys():
        if (
            not form_key_filter(key) or
            key in ('meta', 'case', 'commcare_usercase') or
            key.startswith('case_autoload_') or
            key.startswith('case_load_')
        ):
            data.pop(key)
    return data


def pop_from_form_data(relative_data, absolute_data, path):
    path = path.split('/')
    if path and path[0] == '':
        data = absolute_data
        # path[:2] will be ['', 'data'] so remove
        path = path[2:]
    else:
        data = relative_data

    while path and data:
        key, path = path[0], path[1:]
        try:
            if path:
                data = data[key]
            elif hasattr(data, 'pop'):
                return data.pop(key)
            else:
                return None
        except KeyError:
            return None


def path_relative_to_context(path, path_context):
    assert path_context.endswith('/')
    if path.startswith(path_context):
        return path[len(path_context):]
    elif path + '/' == path_context:
        return ''
    else:
        return path


def absolute_path_from_context(path, path_context):
    assert path_context.endswith('/')
    if path.startswith('/'):
        return path
    else:
        return path_context + path


def _html_interpolate_output_refs(itext_value, context):
    if hasattr(itext_value, 'with_refs'):
        underline_template = u'<u>&nbsp;&nbsp;%s&nbsp;&nbsp;</u>'
        return mark_safe(
            itext_value.with_refs(
                context,
                processor=lambda x: underline_template % (
                    html.escape(x)
                    if x is not None
                    else u'<i class="icon-question-sign"></i>'
                ),
                escape=html.escape,
            )
        )
    else:
        return itext_value


def _group_question_has_response(question):
    return any(child.response for child in question.children)


def zip_form_data_and_questions(relative_data, questions, path_context='',
                                output_context=None, process_label=None,
                                absolute_data=None):
    """
    The strategy here is to loop through the questions, and at every point
    pull in the corresponding piece of data, removing it from data
    and adding it to the question. At the end, any remain piece of data are
    added to the end as unknown questions.

    Repeats are matched up with their entry node in the data,
    and then this function is applied recursively to each of the elements in
    the list, using the repeat's children as the question list.

    """
    assert path_context
    absolute_data = absolute_data or relative_data
    if not path_context.endswith('/'):
        path_context += '/'
    if not output_context:
        output_context = {
            '%s%s' % (path_context, '/'.join(map(unicode, key))): unicode(value)
            for key, value in _flatten_json(relative_data).items()
        }

    result = []
    for question in questions:
        path = path_relative_to_context(question.value, path_context)
        absolute_path = absolute_path_from_context(question.value, path_context)
        node = pop_from_form_data(relative_data, absolute_data, path)
        # response=True on a question with children indicates that one or more
        # child has a response, i.e. that the entire group wasn't skipped
        question_data = dict(question)
        question_data.pop('response')
        if question.type in ('Group', 'FieldList'):
            children = question_data.pop('children')
            form_question = FormQuestionResponse(
                children=zip_form_data_and_questions(
                    node,
                    children,
                    path_context=absolute_path,
                    output_context=output_context,
                    process_label=process_label,
                    absolute_data=absolute_data,
                ),
                **question_data
            )
            if _group_question_has_response(form_question):
                form_question.response = True
        elif question.type == 'Repeat':
            if not isinstance(node, list):
                node = [node]
            children = question_data.pop('children')
            form_question = FormQuestionResponse(
                children=[
                    FormQuestionResponse(
                        children=zip_form_data_and_questions(
                            entry,
                            children,
                            path_context=absolute_path,
                            output_context=output_context,
                            process_label=process_label,
                            absolute_data=absolute_data,
                        ),
                    )
                    for entry in node
                ],
                **question_data
            )
            for child in form_question.children:
                if _group_question_has_response(child):
                    child.response = True
            if _group_question_has_response(form_question):
                form_question.response = True
        else:
            if (question.type == 'DataBindOnly'
                    and question.label == question.value):
                question_data['label'] = '/'.join(
                    question.value.split('/')[2:])

            if process_label:
                question_data['label'] = process_label(question_data['label'],
                                                       output_context)

            form_question = FormQuestionResponse(response=node,
                                                 **question_data)
        result.append(form_question)

    if relative_data:
        for key, response in sorted(_flatten_json(relative_data).items()):
            joined_key = '/'.join(map(unicode, key))
            result.append(
                FormQuestionResponse(
                    label=joined_key,
                    value='%s%s' % (path_context, joined_key),
                    response=response,
                )
            )

    return result


def _flatten_json(json, result=None, path=()):
    if result is None:
        result = {}
    if isinstance(json, dict):
        for key, value in json.items():
            _flatten_json(value, result, path + (key,))
    elif isinstance(json, list):
        for i, value in enumerate(json):
            _flatten_json(value, result, path + (i,))
    else:
        result[path] = json
    return result


def questions_in_hierarchy(questions):
    # It turns out that questions isn't quite enough to reconstruct
    # the hierarchy if there are groups that share the same ref
    # as their parent (like for grouping on the screen but not the data).
    # In this case, ignore nesting and put all sub questions on the top level,
    # along with the group itself.
    # Real solution is to get rid of this function and instead have
    # get_questions preserve hierarchy to begin with
    result = []
    question_lists_by_group = {None: result}
    for question in questions:
        question_lists_by_group[question.group].append(question)
        if question.type in ('Group', 'Repeat', 'FieldList') \
                and question.value not in question_lists_by_group:
            question_lists_by_group[question.value] = question.children
    return question_lists_by_group[None]
