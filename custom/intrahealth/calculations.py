from datetime import timedelta
import logging
from casexml.apps.case.models import CommCareCase
from custom.intrahealth import OPERATEUR_XMLNSES, PAYMENT_XMLNSES
from custom.intrahealth.models import PaymentTracking


def get_payment_month_from_form(form):
    """
    Given a form, pull out the payment month to use, which is the month
    the form was filled in + 30 days
    """
    timestamp = form.metadata.timeEnd + timedelta(days=30)
    return (timestamp.year, timestamp.month)


def get_case_id_from_form(form):
    return form.xpath('form/case/@case_id')


def get_calculated_amount_owed_from_form(form):
    return _safeint(form, 'form/total_amt_owed')


def get_actual_amount_owed_from_form(form):
    return _safeint(form, 'form/actual_amount_owed')


def get_amount_paid_from_form(form):
    return _safeint(form, 'form/amount_paid')


def _safeint(form, xpath):
    try:
        return int(form.xpath(xpath))
    except ValueError:
        logging.exception('unable to get {0} from form {0}'.format(xpath, form['_id']))
        return 0


def payment_model_from_form(form):
    year, month = get_payment_month_from_form(form)
    return PaymentTracking.objects.get_or_create(
        case_id=get_case_id_from_form(form),
        month=month,
        year=year,
    )[0]


def is_operateur_form(form):
    return form.xmlns in OPERATEUR_XMLNSES


def is_payment_form(form):
    return form.xmlns in PAYMENT_XMLNSES


def update_payment_model(payment_model, form):
    if is_operateur_form(form):
        payment_model.calculated_amount_owed += get_calculated_amount_owed_from_form(form)
    elif is_payment_form(form):
        # the payment form overrides whatever was calculated so set it directly
        # don't add
        payment_model.actual_amount_owed = get_actual_amount_owed_from_form(form)
        payment_model.amount_paid += get_amount_paid_from_form(form)


def update_payment_data_from_form(form):
    payment_model = payment_model_from_form(form)
    update_payment_model(payment_model, form)
    payment_model.save()


def rebuild_payment_models(form):
    """
    Given a form - rebuild the payment models associated with it from scratch.
    Necessary in the case of archived or deleted forms.
    """
    payment_model = payment_model_from_form(form)
    payment_model.amount_owed = 0
    payment_model.amount_paid = 0
    case = CommCareCase.get(payment_model.case_id)
    for form in case.get_forms():
        update_payment_model(payment_model, form)
    payment_model.save()
