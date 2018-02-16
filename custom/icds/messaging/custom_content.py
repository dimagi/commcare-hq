from __future__ import absolute_import
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
    HINDI, TELUGU, MARATHI)
from custom.icds.exceptions import CaseRelationshipError
from custom.icds.messaging.indicators import DEFAULT_LANGUAGE
from custom.icds.rules.immunization import (
    get_immunization_products,
    get_immunization_anchor_date,
    get_tasks_case_immunization_ledger_values,
    get_map,
    immunization_is_due,
)
from decimal import Decimal, InvalidOperation
from dimagi.utils.logging import notify_exception
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

GROWTH_MONITORING_XMLNS = 'http://openrosa.org/formdesigner/b183124a25f2a0ceab266e4564d3526199ac4d75'


def notify_exception_and_return_empty_list():
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


def get_state_code(location):
    if not location:
        return None

    state = location.get_ancestors().filter(location_type__code=STATE_TYPE_CODE).first()
    return state.site_code if state else None


def get_language_code_for_state(state_code):
    if state_code == ANDHRA_PRADESH_SITE_CODE:
        return TELUGU
    elif state_code == MAHARASHTRA_SITE_CODE:
        return MARATHI
    else:
        return HINDI


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
    except CaseRelationshipError:
        return notify_exception_and_return_empty_list()

    try:
        weight_prev = Decimal(form.form_data.get('weight_prev'))
    except (InvalidOperation, TypeError):
        return notify_exception_and_return_empty_list()

    try:
        weight_child = Decimal(form.form_data.get('weight_child'))
    except (InvalidOperation, TypeError):
        return notify_exception_and_return_empty_list()

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


def render_content_for_user(user, template, context):
    state_code = get_state_code(user.location)
    language_code = get_language_code_for_state(state_code)
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
    except CaseRelationshipError:
        return notify_exception_and_return_empty_list()

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
    except CaseRelationshipError:
        return notify_exception_and_return_empty_list()

    context = {
        'beneficiary': mother_case.name,
    }
    return [render_content_for_user(recipient, 'cf_visits_complete.txt', context)]


def dpt3_and_measles_are_due(recipient, case_schedule_instance):
    """
    Check if the DPT3 and Measles vaccinations are both due, and if so return the
    reminder message.
    """
    case = case_schedule_instance.case
    if case.type != 'tasks':
        raise ValueError("Expected 'tasks' case")

    if case.get_case_property('tasks_type') != 'child':
        raise ValueError("Expected 'tasks_type' of 'child'")

    products = get_immunization_products(case_schedule_instance.domain, 'child')
    product_code_to_product = get_map(products, 'code')
    dpt3_product = product_code_to_product['3g_dpt_3']
    measles_product = product_code_to_product['4g_measles']

    ledger_values = get_tasks_case_immunization_ledger_values(case)
    anchor_date = get_immunization_anchor_date(case)
    if (
        immunization_is_due(case, anchor_date, dpt3_product, products, ledger_values) and
        immunization_is_due(case, anchor_date, measles_product, products, ledger_values)
    ):
        child_person_case = child_person_case_from_tasks_case(case)

        if person_case_is_migrated_or_opted_out(child_person_case):
            return []

        context = {
            'child_name': child_person_case.name,
        }
        return [render_content_for_user(recipient, 'dpt3_and_measles_due.txt', context)]

    return []


def child_vaccinations_complete(recipient, case_schedule_instance):
    case = case_schedule_instance.case
    if case.type != 'tasks':
        raise ValueError("Expected 'tasks' case")

    try:
        child_person_case = child_person_case_from_tasks_case(case)
    except CaseRelationshipError:
        return notify_exception_and_return_empty_list()

    context = {
        'child_name': child_person_case.name,
    }
    return [render_content_for_user(recipient, 'child_vaccinations_complete.txt', context)]
