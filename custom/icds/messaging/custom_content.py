from corehq.apps.users.models import CommCareUser
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.models import XFormInstanceSQL
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from custom.icds.const import (STATE_TYPE_CODE, ANDHRA_PRADESH_SITE_CODE, MAHARASHTRA_SITE_CODE,
    HINDI, TELUGU, MARATHI)
from custom.icds.messaging.custom_recipients import (
    get_child_health_host_case,
    mother_person_case_from_ccs_record_case,
)
from custom.icds.messaging.indicators import DEFAULT_LANGUAGE
from decimal import Decimal, InvalidOperation
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

GROWTH_MONITORING_XMLNS = 'http://openrosa.org/formdesigner/b183124a25f2a0ceab266e4564d3526199ac4d75'


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
    form = get_last_growth_monitoring_form(schedule_instance.domain, schedule_instance.case_id)
    if not form:
        return []

    host_case = get_child_health_host_case(schedule_instance.domain, schedule_instance.case_id)
    if not host_case:
        return []

    try:
        weight_prev = Decimal(form.form_data.get('weight_prev'))
    except (InvalidOperation, TypeError):
        return []

    try:
        weight_child = Decimal(form.form_data.get('weight_child'))
    except (InvalidOperation, TypeError):
        return []

    if weight_child > weight_prev:
        return []
    elif weight_child == weight_prev:
        template = 'beneficiary_static_growth.txt'
    else:
        # weight_child < weight_prev
        template = 'beneficiary_negative_growth.txt'

    language_code = recipient.get_language_code() or DEFAULT_LANGUAGE
    context = {'child_name': host_case.name}
    return [render_message(language_code, template, context)]


def render_content_for_user(user, template, context):
    state_code = get_state_code(user.location)
    language_code = get_language_code_for_state(state_code)
    return render_message(language_code, template, context)


def render_missed_visit_message(recipient, case_schedule_instance, template):
    if not isinstance(recipient, CommCareUser):
        return []

    mother_case = mother_person_case_from_ccs_record_case(case_schedule_instance)

    context = {
        'awc': case_schedule_instance.case_owner.name if case_schedule_instance.case_owner else '',
        'beneficiary': mother_case.name if mother_case else '',
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

    if case_schedule_instance.case.type != 'ccs_record':
        raise ValueError("Expected 'ccs_record' case")

    mother_case = mother_person_case_from_ccs_record_case(case_schedule_instance)
    if not mother_case:
        return []

    context = {
        'beneficiary': mother_case.name,
    }
    return [render_content_for_user(recipient, 'cf_visits_complete.txt', context)]
