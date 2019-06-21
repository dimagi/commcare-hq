from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_noop
import dateutil
from corehq.apps.app_manager.dbaccessors import get_latest_build_id, get_latest_released_build_id
from corehq.apps.domain.models import Domain
from datetime import timedelta
from pytz import timezone
import six

from corehq.util.python_compatibility import soft_assert_type_text

EMPTY_FIELD = "---"
SUCCEED_DOMAIN = 'succeed'
SUCCEED_CM_APPNAME = 'SUCCEED CM app'
SUCCEED_PM_APPNAME = 'SUCCEED PM app'
SUCCEED_CHW_APPNAME = 'SUCCEED CHW app'

CONFIG = {
    'groups': [
        dict(val="harbor", text=ugettext_noop("Harbor UCLA")),
        dict(val="lac-usc", text=ugettext_noop("LAC-USC")),
        dict(val="oliveview", text=ugettext_noop("Olive View Medical Center")),
        dict(val="rancho", text=ugettext_noop("Rancho Los Amigos")),
    ],
    'succeed_admin': 'SUCCEED Admin',
    'pm_role': 'Project Manager',
    'pi_role': 'Principal Investigator',
    'cm_role': 'Care Manager',
    'chw_role': 'Community Health Worker'
}


def has_role(user, roles):
    return user.get_role() is not None and user.get_role()['name'] in roles


def is_succeed_admin(user):
    return has_role(user, [CONFIG['succeed_admin'], 'Admin'])


def is_pi(user):
    return has_role(user, [CONFIG['pi_role']])


def is_cm(user):
    return has_role(user, [CONFIG['cm_role']])


def is_chw(user):
    return has_role(user, [CONFIG['chw_role']])


def is_pm_or_pi(user):
    return has_role(user, [CONFIG['pm_role'], CONFIG['pi_role']])


def has_any_role(user):
    return is_chw(user) or is_pm_or_pi(user) or is_cm(user)


def get_app_build(app_dict):
    domain = Domain.get_by_name(app_dict['domain'])
    if domain.use_cloudcare_releases:
        return get_latest_released_build_id(app_dict['domain'], app_dict['_id'])
    else:
        return get_latest_build_id(app_dict['domain'], app_dict['_id'])


def get_form_dict(case, form_xmlns):
    forms = case.get_forms()
    for form in forms:
        form_dict = form.form
        if form_xmlns == form_dict["@xmlns"]:
            return form_dict
    return None


def format_date(date_string, OUTPUT_FORMAT, localize=None):
    if date_string is None or date_string == '' or date_string == " " or date_string == EMPTY_FIELD \
            or isinstance(date_string, (int, float)):
        return ''

    if isinstance(date_string, six.string_types):
        soft_assert_type_text(date_string)
        try:
            date_string = dateutil.parser.parse(date_string)
        except (AttributeError, ValueError):
            return ''

    if localize:
        tz = Domain.get_by_name(SUCCEED_DOMAIN).get_default_timezone()
        if date_string.tzname() is None:
            date_string = timezone('UTC').localize(date_string)
        date_string = date_string.astimezone(tz)

    return date_string.strftime(OUTPUT_FORMAT)


def get_randomization_date(case):
    from custom.succeed.reports import INPUT_DATE_FORMAT
    rand_date = case.get_case_property("randomization_date")
    if rand_date != None:
        date = format_date(rand_date, INPUT_DATE_FORMAT)
        return date
    else:
        return EMPTY_FIELD


def update_patient_target_dates(case):
    from custom.succeed.reports import VISIT_SCHEDULE

    for visit_key, visit in enumerate(VISIT_SCHEDULE):
        try:
            next_visit = VISIT_SCHEDULE[visit_key + 1]
        except IndexError:
            next_visit = 'last'
        if next_visit != 'last' and case.get_case_property("randomization_date") is not None:
            rand_date = dateutil.parser.parse(get_randomization_date(case))
            tg_date = rand_date.date() + timedelta(days=next_visit['days'])
            # technically updates to cases should only happen via form submissions
            # leaving as is for now since this is custom code
            # SK 2016-02-03
            setattr(case, visit['target_date_case_property'], tg_date.strftime("%m/%d/%Y"))
    case.save()
