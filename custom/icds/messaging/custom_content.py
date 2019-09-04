from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.users.cases import get_owner_id, get_wrapped_owner
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.models import XFormInstanceSQL
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from custom.icds.case_relationships import (
    child_person_case_from_tasks_case,
    child_person_case_from_child_health_case,
    mother_person_case_from_ccs_record_case,
)
from custom.icds.const import (STATE_TYPE_CODE, ANDHRA_PRADESH_SITE_CODE, MAHARASHTRA_SITE_CODE,
    HINDI, TELUGU, MARATHI, AWC_LOCATION_TYPE_CODE, SUPERVISOR_LOCATION_TYPE_CODE)
from custom.icds.exceptions import CaseRelationshipError
from custom.icds.messaging.custom_recipients import skip_notifying_missing_ccs_record_parent
from custom.icds.messaging.indicators import (
    DEFAULT_LANGUAGE,
    AWWIndicator,
    LSIndicator,
    AWWSubmissionPerformanceIndicator,
    AWWAggregatePerformanceIndicator,
    AWWVHNDSurveyIndicator,
    LSAggregatePerformanceIndicator,
    LSVHNDSurveyIndicator,
    LSSubmissionPerformanceIndicator,
)
from decimal import Decimal, InvalidOperation
from dimagi.utils.logging import notify_exception
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

GROWTH_MONITORING_XMLNS = 'http://openrosa.org/formdesigner/b183124a25f2a0ceab266e4564d3526199ac4d75'


def notify_exception_and_return_empty_list(e):
    if not (
        isinstance(e, CaseRelationshipError) and
        skip_notifying_missing_ccs_record_parent(e)
    ):
        notify_exception(
            None,
            message="Error with ICDS custom content handler",
        )

    return []


def get_last_growth_monitoring_form(domain, case_id):
    transactions = CaseAccessorSQL.get_transactions_for_case_rebuild(case_id)
    form_ids = [t.form_id for t in transactions if t.form_id]

    forms_under_consideration = []

    db_names = get_db_aliases_for_partitioned_query()
    for db_name in db_names:
        result = XFormInstanceSQL.objects.using(db_name).filter(
            domain=domain,
            form_id__in=form_ids,
            xmlns=GROWTH_MONITORING_XMLNS,
            state=XFormInstanceSQL.NORMAL,
        ).order_by('-received_on').first()
        if result:
            forms_under_consideration.append(result)

    if not forms_under_consideration:
        return None

    forms_under_consideration.sort(key=lambda form: form.received_on, reverse=True)
    return forms_under_consideration[0]


def render_message(language_code, template, context):
    try:
        message = render_to_string('icds/messaging/indicators/%s/%s' % (language_code, template), context)
    except TemplateDoesNotExist:
        message = render_to_string('icds/messaging/indicators/%s/%s' % (DEFAULT_LANGUAGE, template), context)

    return message.strip()


def static_negative_growth_indicator(recipient, schedule_instance):
    if schedule_instance.case.get_case_property('zscore_grading_wfa') == 'red':
        # If the child currently has a red score, do not send this message.
        # We check this here instead of checking it as part of the rule criteria
        # because if we checked it in the rule critiera, then the message would
        # send as soon as the score becomes yellow which we don't want. We just
        # want to skip sending it if it's red at the time this message is supposed
        # to send.
        return []

    form = get_last_growth_monitoring_form(schedule_instance.domain, schedule_instance.case_id)
    if not form:
        return []

    try:
        child_person_case = child_person_case_from_child_health_case(schedule_instance.case)
    except CaseRelationshipError as e:
        return notify_exception_and_return_empty_list(e)

    try:
        weight_prev = Decimal(form.form_data.get('weight_prev'))
    except (InvalidOperation, TypeError) as e:
        return notify_exception_and_return_empty_list(e)

    try:
        weight_child = Decimal(form.form_data.get('weight_child'))
    except (InvalidOperation, TypeError) as e:
        return notify_exception_and_return_empty_list(e)

    if weight_child > weight_prev:
        return []
    elif weight_child == weight_prev:
        template = 'beneficiary_static_growth.txt'
    else:
        # weight_child < weight_prev
        template = 'beneficiary_negative_growth.txt'

    language_code = recipient.get_language_code() or DEFAULT_LANGUAGE
    context = {'child_name': child_person_case.name}
    return [render_message(language_code, template, context)]


def get_user_from_usercase(usercase):
    user = get_wrapped_owner(get_owner_id(usercase))
    if not isinstance(user, CommCareUser):
        return None

    return user


def render_content_for_user(user, template, context):
    if user.memoized_usercase:
        language_code = user.memoized_usercase.get_language_code() or DEFAULT_LANGUAGE
    else:
        language_code = DEFAULT_LANGUAGE

    return render_message(language_code, template, context)


def person_case_is_migrated(case):
    """
    Applies to both person cases representing mothers and person cases representing children.
    Returns True if the person is marked as having migrated to another AWC, otherwise False.
    """
    return case.get_case_property('migration_status') == 'migrated'


def person_case_opted_out(case):
    """
    Applies to both person cases representing mothers and person cases representing children.
    Returns True if the person is marked as having opted out of services, otherwise False.
    """
    return case.get_case_property('registered_status') == 'not_registered'


def person_case_is_migrated_or_opted_out(case):
    return person_case_is_migrated(case) or person_case_opted_out(case)


def render_missed_visit_message(recipient, case_schedule_instance, template):
    if not isinstance(recipient, CommCareUser):
        return []

    try:
        mother_case = mother_person_case_from_ccs_record_case(case_schedule_instance.case)
    except CaseRelationshipError as e:
        return notify_exception_and_return_empty_list(e)

    if person_case_is_migrated_or_opted_out(mother_case):
        return []

    if case_schedule_instance.case_owner is None:
        return []

    context = {
        'awc': case_schedule_instance.case_owner.name,
        'beneficiary': mother_case.name,
    }

    return [render_content_for_user(recipient, template, context)]


def missed_cf_visit_to_aww(recipient, case_schedule_instance):
    return render_missed_visit_message(recipient, case_schedule_instance, 'missed_cf_visit_to_aww.txt')


def missed_cf_visit_to_ls(recipient, case_schedule_instance):
    return render_missed_visit_message(recipient, case_schedule_instance, 'missed_cf_visit_to_ls.txt')


def missed_pnc_visit_to_ls(recipient, case_schedule_instance):
    return render_missed_visit_message(recipient, case_schedule_instance, 'missed_pnc_visit_to_ls.txt')


def child_illness_reported(recipient, case_schedule_instance):
    if not isinstance(recipient, CommCareUser) or not case_schedule_instance.case:
        return []

    if case_schedule_instance.case.type != 'person':
        raise ValueError("Expected 'person' case")

    context = {
        'awc': case_schedule_instance.case_owner.name if case_schedule_instance.case_owner else '',
        'child': case_schedule_instance.case.name,
    }
    return [render_content_for_user(recipient, 'child_illness_reported.txt', context)]


def cf_visits_complete(recipient, case_schedule_instance):
    if not isinstance(recipient, CommCareUser) or not case_schedule_instance.case:
        return []

    try:
        mother_case = mother_person_case_from_ccs_record_case(case_schedule_instance.case)
    except CaseRelationshipError as e:
        return notify_exception_and_return_empty_list(e)

    context = {
        'beneficiary': mother_case.name,
    }
    return [render_content_for_user(recipient, 'cf_visits_complete.txt', context)]


def validate_user_location_and_indicator(user, indicator_class):
    if issubclass(indicator_class, AWWIndicator):
        if user.location.location_type.code != AWC_LOCATION_TYPE_CODE:
            raise TypeError("Expected AWWIndicator to be called for an AWW, got %s instead" % user.get_id)
    elif issubclass(indicator_class, LSIndicator):
        if user.location.location_type.code != SUPERVISOR_LOCATION_TYPE_CODE:
            raise TypeError("Expected LSIndicator to be called for an LS, got %s instead" % user.get_id)
    else:
        raise TypeError("Expected AWWIndicator or LSIndicator")


def run_indicator_for_user(user, indicator_class, language_code=None):
    validate_user_location_and_indicator(user, indicator_class)
    indicator = indicator_class(user.domain, user)
    return indicator.get_messages(language_code=language_code)


def run_indicator_for_usercase(usercase, indicator_class):
    if usercase.type != USERCASE_TYPE:
        raise ValueError("Expected '%s' case" % USERCASE_TYPE)

    user = get_user_from_usercase(usercase)
    if user and user.location:
        return run_indicator_for_user(user, indicator_class, language_code=usercase.get_language_code())

    return []


def aww_1(recipient, case_schedule_instance):
    return run_indicator_for_usercase(case_schedule_instance.case, AWWSubmissionPerformanceIndicator)


def aww_2(recipient, case_schedule_instance):
    return run_indicator_for_usercase(case_schedule_instance.case, AWWAggregatePerformanceIndicator)


def phase2_aww_1(recipient, case_schedule_instance):
    return run_indicator_for_usercase(case_schedule_instance.case, AWWVHNDSurveyIndicator)


def ls_1(recipient, case_schedule_instance):
    return run_indicator_for_usercase(case_schedule_instance.case, LSAggregatePerformanceIndicator)


def ls_2(recipient, case_schedule_instance):
    return run_indicator_for_usercase(case_schedule_instance.case, LSVHNDSurveyIndicator)


def ls_6(recipient, case_schedule_instance):
    return run_indicator_for_usercase(case_schedule_instance.case, LSSubmissionPerformanceIndicator)
