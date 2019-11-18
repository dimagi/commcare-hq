from casexml.apps.case.models import CommCareCase
from memoized import memoized
from corehq.apps.users.models import CommCareUser
from .constants import EMPTY_FIELD
from custom.m4change.models import McctStatus


@memoized
def get_case_by_id(case_id):
    return CommCareCase.get(case_id)


@memoized
def get_user_by_id(user_id):
    return CommCareUser.get(user_id)


def get_property(dict_obj, name, default=None):
    if name in dict_obj:
        if type(dict_obj[name]) is dict:
            return dict_obj[name]["#value"]
        return dict_obj[name]
    else:
        return default if default is not None else EMPTY_FIELD


def get_form_ids_by_status(domain, status):
    return [item.form_id for item in McctStatus.objects.filter(domain=domain, status=status)]

