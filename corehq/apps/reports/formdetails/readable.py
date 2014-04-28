from collections import defaultdict
from django.http import Http404
from jsonobject import *
from jsonobject.base import DefaultProperty
from corehq.apps.app_manager.models import get_app, Application
from corehq.apps.app_manager.xform import VELLUM_TYPES
from corehq.apps.reports.formdetails.exceptions import QuestionListNotFound


class FormQuestionOption(JsonObject):
    label = StringProperty()
    value = StringProperty()


class FormQuestion(JsonObject):
    label = StringProperty()
    tag = StringProperty()
    type = StringProperty(choices=VELLUM_TYPES.keys())
    value = StringProperty()
    repeat = StringProperty()
    group = StringProperty()
    options = ListProperty(FormQuestionOption, exclude_if_none=True)

    @property
    def icon(self):
        return VELLUM_TYPES[self.type]['icon']


class HierarchicalFormQuestion(FormQuestion):
    children = ListProperty(lambda: HierarchicalFormQuestion,
                            exclude_if_none=True)


class FormQuestionResponse(HierarchicalFormQuestion):
    response = DefaultProperty()

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


def get_readable_form_data(xform):
    app_id = xform.build_id or xform.app_id
    domain = xform.domain
    xmlns = xform.xmlns
    try:
        app = get_app(domain, app_id)
    except Http404:
        raise QuestionListNotFound(
            "No app with id {} could be found".format(app_id)
        )
    if not isinstance(app, Application):
        raise QuestionListNotFound(
            "The app we found for id {} is not a {}, which are not supported."
            .format(app_id, app.__class__.__name__)
        )
    form = app.get_form_by_xmlns(xmlns)
    questions = form.wrapped_xform().get_questions(
        app.langs, include_triggers=True, include_groups=True)
    questions = [FormQuestion(q) for q in questions]
    return questions_in_hierarchy(
        zip_form_data_and_questions(xform.form, questions)
    )


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


def zip_form_data_and_questions(data, questions):
    result = []
    # remove all case, meta, attribute nodes from the top level
    for key in data.keys():
        if key.startswith(('#', '@')) or key in ('meta', 'case'):
            data.pop(key)
    flat_data = _flatten_json(data)
    for question in questions:
        # value.split('/') will always look like
        # ('', 'data', 'question1', ...)
        # so strip off first two items
        key = tuple(question.value.split('/')[2:])
        if question.tag == 'hidden':
            question.label = '/'.join(key)
        try:
            response = flat_data.pop(key) or ''
        except KeyError:
            response = None
        result.append(
            FormQuestionResponse(response=response, **question)
        )
    return result


def questions_in_hierarchy(questions):
    partition = defaultdict(list)
    for question in questions:
        partition[question.group].append(question)
    for question in questions:
        if question.type in ('Group', 'Repeat'):
            question.children = partition.pop(question.value)
    return partition[None]
