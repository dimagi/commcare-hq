from corehq.apps.users.models import CommCareCase


def get_case_id(form):
    case_dict = form.form.get('case')
    if not case_dict:
        return None
    return case_dict.get('@case_id')


def get_case_property(form, property_name):
    case_dict = form.form.get('case')
    if not case_dict:
        return None
    case_id = case_dict.get('@case_id')
    if not case_id:
        return None
    case = CommCareCase.get(case_id)
    return case.get_case_property(property_name)
