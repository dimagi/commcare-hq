from corehq.apps.userreports.specs import TypeProperty
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
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
    (99, 99): "Other",
}


def get_val(form, path, default=0):
    if not form:
        return default
    question_value = form.get_data(path)
    try:
        return int(question_value)
    except (ValueError, TypeError):
        return default


def get_yes_no(yes, no):
    if yes:
        return 'Yes'
    elif no:
        return 'No'
    else:
        return 'N/A'


class EQAExpressionSpec(JsonObject):
    type = TypeProperty('eqa_expression')
    question_id = StringProperty()
    tally_yes_id = StringProperty()
    tally_no_id = StringProperty()
    display_text = StringProperty()
    xmlns = StringProperty()

    def __call__(self, item, context=None):
        xforms_ids = CaseAccessors(item['domain']).get_case_xform_ids(item['_id'])
        forms = FormAccessors(item['domain']).get_forms(xforms_ids)
        f_forms = [f for f in forms if f.xmlns == self.xmlns]
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

        path_question = 'form/%s' % self.question_id
        path_yes = 'form/%s' % self.tally_yes_id
        path_no = 'form/%s' % self.tally_no_id

        curr_ques = get_val(curr_form, path_question, 99)
        curr_sub_yes = get_val(curr_form, path_yes)
        curr_sub_no = get_val(curr_form, path_no)
        prev_ques = get_val(prev_form, path_question, 99)
        prev_sub_yes = get_val(prev_form, path_yes)
        prev_sub_no = get_val(prev_form, path_no)

        return {
            'question_id': self.question_id,
            'display_text': self.display_text,
            'current_submission': get_yes_no(curr_sub_yes, curr_sub_no),
            'previous_submission': get_yes_no(prev_sub_yes, prev_sub_no),
            'status': STATUSES.get((curr_ques, prev_ques))
        }


def eqa_expression(spec, context):
    wrapped = EQAExpressionSpec.wrap(spec)
    return wrapped
