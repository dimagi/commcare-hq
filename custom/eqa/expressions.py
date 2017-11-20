from __future__ import absolute_import
from corehq.apps.app_manager.models import Application
from corehq.apps.userreports.specs import TypeProperty
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.util.quickcache import quickcache
from dimagi.ext.jsonobject import JsonObject, StringProperty


STATUSES = {
    (1, 0): "Improved",
    (0, 1): "**Declined**",
    (1, 1): "Satisfactory",
    (0, 0): "**Needs improvement**",
    (99, 0): "**Needs improvement**",
    (0, 99): "**Needs improvement**",
    (99, 1): "Satisfactory",
    (1, 99): "Satisfactory",
    (99, 99): "N/A",
}


def get_val(form, path, default=0, data_type=None):
    if not form:
        return data_type(default)
    question_value = form.get_data(path)
    try:
        return data_type(question_value)
    except (ValueError, TypeError):
        return data_type(default)


def get_yes_no(val):
    if val == 1:
        return 'Yes'
    elif val == 0:
        return 'No'
    else:
        return 'N/A'


@quickcache(['item', 'xmlns'])
def get_two_last_forms(item, xmlns):
    xforms_ids = CaseAccessors(item['domain']).get_case_xform_ids(item['_id'])
    forms = FormAccessors(item['domain']).get_forms(xforms_ids)
    f_forms = [f for f in forms if f.xmlns == xmlns]
    s_forms = sorted(f_forms, key=lambda x: x.received_on)

    if len(s_forms) >= 2:
        curr_form = s_forms[-1]
        prev_form = s_forms[-2]
    elif len(s_forms) == 1:
        curr_form = s_forms[-1]
        prev_form = None
    else:
        curr_form = None
        prev_form = None

    return curr_form, prev_form


class EQAExpressionSpec(JsonObject):
    type = TypeProperty('eqa_expression')
    question_id = StringProperty()
    display_text = StringProperty()
    xmlns = StringProperty()

    def __call__(self, item, context=None):
        curr_form, prev_form = get_two_last_forms(item, self.xmlns)

        path_question = 'form/%s' % self.question_id

        curr_ques = get_val(curr_form, path_question, 99, int)
        prev_ques = get_val(prev_form, path_question, 99, int)

        return {
            'question_id': self.question_id,
            'display_text': self.display_text,
            'current_submission': get_yes_no(curr_ques),
            'previous_submission': get_yes_no(prev_ques),
            'status': STATUSES.get((curr_ques, prev_ques), "N/A")
        }


class EQAActionItemSpec(JsonObject):
    type = TypeProperty('cqi_action_item')
    xmlns = StringProperty()
    section = StringProperty()
    question_id = StringProperty()

    def __call__(self, item, context=None):
        xforms_ids = CaseAccessors(item['domain']).get_case_xform_ids(item['_id'])
        forms = FormAccessors(item['domain']).get_forms(xforms_ids)
        f_forms = [f for f in forms if f.xmlns == self.xmlns]
        s_forms = sorted(f_forms, key=lambda x: x.received_on)

        if len(s_forms) > 0:
            latest_form = s_forms[-1]
        else:
            latest_form = None
        path_to_action_plan = 'form/action_plan/%s/action_plan' % self.section

        if latest_form:
            action_plans = latest_form.get_data(path_to_action_plan)
            if action_plans:
                action_plan_for_question = None
                for action_plan in action_plans:
                    if action_plan.get('incorrect_questions', '') == self.question_id:
                        action_plan_for_question = action_plan
                        break
                if action_plan_for_question:
                    incorrect_question = action_plan_for_question.get('incorrect_questions', '')
                    responsible = ', '.join(
                        [
                            item.get(x.strip(), '---') for x in
                            action_plan_for_question.get('action_plan_input', {}).get('responsible', '').split(',')
                        ]
                    )
                    support = ', '.join(
                        [
                            item.get(x.strip(), '---') for x in
                            action_plan_for_question.get('action_plan_input', {}).get('support', '').split(',')
                        ]
                    )
                    application = Application.get(latest_form.app_id)
                    form = application.get_forms_by_xmlns(self.xmlns)[0]
                    question_list = application.get_questions(self.xmlns)
                    questions = {x['value']: x for x in question_list}
                    return {
                        'form_name': form.name['en'],
                        'section': self.section,
                        'timeEnd': latest_form.metadata.timeEnd,
                        'gap': questions.get('data/code_to_text/%s' % incorrect_question, {}).get('label', '---'),
                        'intervention_action': action_plan_for_question.get('intervention_action', '---'),
                        'responsible': responsible,
                        'support': support,
                        'deadline': action_plan_for_question.get('DEADLINE', '---'),
                        'notes': action_plan_for_question.get('notes', '---'),
                    }


class EQAPercentExpression(JsonObject):
    type = TypeProperty('eqa_percent_expression')
    question_id = StringProperty()
    display_text = StringProperty()
    xmlns = StringProperty()

    def __call__(self, item, context=None):
        curr_form, prev_form = get_two_last_forms(item, self.xmlns)

        path_question = 'form/%s' % self.question_id

        curr_ques = get_val(curr_form, path_question, -1, float)
        prev_ques = get_val(prev_form, path_question, -1, float)

        if curr_ques == -1 or prev_ques == -1:
            status = "N/A"
        elif curr_ques > prev_ques:
            status = "Improved"
        elif curr_ques < prev_ques:
            status = "Declined"
        else:
            status = "Satisfactory"

        return {
            'question_id': self.question_id,
            'display_text': self.display_text,
            'current_submission': "%.2f%%" % curr_ques if curr_ques != -1 else "N/A",
            'previous_submission': "%.2f%%" % prev_ques if prev_ques != -1 else "N/A",
            'status': status
        }


def eqa_expression(spec, context):
    wrapped = EQAExpressionSpec.wrap(spec)
    return wrapped


def cqi_action_item(spec, context):
    wrapped = EQAActionItemSpec.wrap(spec)
    return wrapped


def eqa_percent_expression(spec, context):
    wrapped = EQAPercentExpression.wrap(spec)
    return wrapped
