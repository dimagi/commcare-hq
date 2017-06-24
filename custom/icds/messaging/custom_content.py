from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.models import XFormInstanceSQL
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from custom.icds.messaging.custom_recipients import get_child_health_host_case
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

    try:
        message = render_to_string('icds/messaging/indicators/%s/%s' % (language_code, template), context)
    except TemplateDoesNotExist:
        message = render_to_string('icds/messaging/indicators/%s/%s' % (DEFAULT_LANGUAGE, template), context)

    return [message.strip()]
