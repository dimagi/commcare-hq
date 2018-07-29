from __future__ import absolute_import
from __future__ import unicode_literals
from custom.enikshay.messaging.custom_recipients import person_case_from_voucher_case
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string


def render_message(language_code, default_language_code, template, context):
    try:
        message = render_to_string('enikshay/sms/%s/%s' % (language_code, template), context)
    except TemplateDoesNotExist:
        message = render_to_string('enikshay/sms/%s/%s' % (default_language_code, template), context)

    return message.strip()


def render_prescription_voucher_alert_content(voucher_case, person_case, recipient, default_langauge_code):
    context = {
        'voucher_id': voucher_case.get_case_property('voucher_id') or '(?)',
        'person_name': person_case.name or '(?)',
        'person_id': person_case.get_case_property('person_id') or '(?)',
    }
    return render_message(
        recipient.get_language_code(),
        default_langauge_code,
        'prescription_voucher_creation.txt',
        context
    )


def prescription_voucher_alert(reminder, handler, recipient):
    voucher_case = reminder.case
    person_case = person_case_from_voucher_case(handler, reminder)
    if person_case:
        return render_prescription_voucher_alert_content(
            voucher_case,
            person_case,
            recipient,
            handler.default_lang
        )

    return None
