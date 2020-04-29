from corehq.apps.app_manager.const import USERCASE_TYPE
from custom.icds.case_relationships import (
    child_person_case_from_child_health_case,
    child_person_cases_from_mother_person_case,
    mother_person_case_from_ccs_record_case,
)
from custom.icds.const import AWC_LOCATION_TYPE_CODE, SUPERVISOR_LOCATION_TYPE_CODE
from custom.icds.messaging.custom_content import get_user_from_usercase, person_case_is_migrated_or_opted_out
from custom.icds.rules.util import get_date, todays_date
from dateutil.relativedelta import relativedelta


def person_case_is_under_6_years_old(case, now):
    """
    NOTE: Use this custom criteria with caution for SMS alerts.
    See `person_case_is_under_n_years_old` for explanation.
    """
    return person_case_is_under_n_years_old(case, now, 6)


def person_case_is_under_19_years_old(case, now):
    """
    NOTE: Use this custom criteria with caution for SMS alerts.
    See `person_case_is_under_n_years_old` for explanation.
    """
    return person_case_is_under_n_years_old(case, now, 19)


def person_case_is_under_n_years_old(case, now, n_years):
    """
    This custom criteria is fine to use with auto case update rules because
    those get run every day so the rule will be responsive to changes in today's date.
    For an auto case update rule, you actually wouldn't even need this custom
    criteria because you could just use one of the date criteria for the rule
    out of the box.

    But for rules that spawn conditional SMS alerts (i.e., those with
    workflow=WORKFLOW_SCHEDULING), we need to be careful about using criteria
    that reference today's date, because those don't run every day - they
    only run when the case changes. So those rules can't be responsive to changes in
    today's date, and that's why date criteria are not allowed in rules that
    spawn SMS alerts.

    For this criteria specifically, that means that you shouldn't use it to
    spawn an alert that repeats for a long period of time because the person
    might not be under N years of age for the entire duration of the schedule,
    or the schedule would stop erratically at the first case update that happens
    after the person's Nth birthday.

    But if you're just using this specific criteria to spawn a one-time alert
    that sends only when it first matches the case, it can be ok. And that only
    works because we're checking that today's date is less than some fixed value.
    If we were checking that today's date is greater than some fixed value, it
    likely wouldn't produce the desired behavior.
    """
    if case.type != 'person':
        return False

    try:
        dob = get_date(case.get_case_property('dob'))
    except Exception:
        return False

    return todays_date(now) < (dob + relativedelta(years=n_years))


def ccs_record_case_has_future_edd(case, now):
    """
    NOTE: This criteria references today's date.
    Use this custom criteria with caution for SMS alerts.
    See `person_case_is_under_n_years_old` for explanation.
    """
    if case.type != 'ccs_record':
        return False

    try:
        edd = get_date(case.get_case_property('edd'))
    except Exception:
        return False

    return todays_date(now) < edd


def ccs_record_case_is_availing_services(case, now):
    """
    This filters to ccs record cases where the relevant child person case is both registered and not migrated.
    """
    mother = mother_person_case_from_ccs_record_case(case)
    children = child_person_cases_from_mother_person_case(mother)

    add = case.get_case_property('add')
    children = [child for child in children if child.get_case_property('dob') == add]

    if not children:
        return False

    return any([
        not(person_case_is_migrated_or_opted_out(child))
        for child in children
    ])


def child_health_case_is_availing_services(case, now):
    """
    This filters to child health cases where the relevant child person case is both registered and not migrated.
    """
    child = child_person_case_from_child_health_case(case)
    if person_case_is_migrated_or_opted_out(child):
        return False

    return case


def check_user_location_type(usercase, location_type_code):
    user = get_user_from_usercase(usercase)
    if user and user.location:
        return user.location.location_type.code == location_type_code

    return False


def is_usercase_of_aww(case, now):
    return case.type == USERCASE_TYPE and check_user_location_type(case, AWC_LOCATION_TYPE_CODE)


def is_usercase_of_ls(case, now):
    return case.type == USERCASE_TYPE and check_user_location_type(case, SUPERVISOR_LOCATION_TYPE_CODE)
