from __future__ import absolute_import
from __future__ import unicode_literals

from collections import defaultdict
from datetime import date

from celery.schedules import crontab
from celery.task import periodic_task

from django.conf import settings

from corehq.apps.accounting.models import Currency
from corehq.apps.smsbillables.models import (
    SmsBillable,
    SmsGatewayFeeCriteria,
)
from corehq.util.log import send_HTML_email
from dimagi.utils.dates import add_months_to_date


@periodic_task(serializer='pickle', run_every=crontab(day_of_month='1', hour=13, minute=0), queue='background_queue', acks_late=True)
def send_gateway_fee_report_out():
    backend_api_ids = SmsGatewayFeeCriteria.objects.values_list('backend_api_id', flat=True).distinct()
    first_day_previous_month = add_months_to_date(date.today(), -1)
    billables_in_month = SmsBillable.objects.filter(
        date_sent__year=first_day_previous_month.year,
        date_sent__month=first_day_previous_month.month,
        is_valid=True,
    )

    costs_by_backend = defaultdict(list)
    for backend_api_id in backend_api_ids:
        billables_in_month_by_backend_api_id = billables_in_month.filter(
            gateway_fee__criteria__backend_api_id=backend_api_id
        )
        relevant_currencies = [
            Currency.objects.get(id=id)
            for id in billables_in_month_by_backend_api_id.values_list(
                'gateway_fee__currency', flat=True).distinct()
        ]
        for currency in relevant_currencies:
            cost_by_backend_and_currency = sum(
                billable.gateway_charge * (billable.gateway_fee_conversion_rate or 1)
                for billable in billables_in_month_by_backend_api_id.filter(
                    gateway_fee__currency=currency
                )
            )
            costs_by_backend[backend_api_id].append((cost_by_backend_and_currency, currency.code))

    subject = "[{}] Cost per SMS Gateway Monthly Summary".format(settings.SERVER_ENVIRONMENT)

    send_HTML_email(
        subject,
        'npellegrino' + '@' + 'dimagi' + '.com',
        ''.join(
            '<p>{}: {}</p>'.format(
                backend_api_id, '; '.join(
                    '%.2f %s (%.2f %s)' % (
                        cost,
                        currency_code,
                        cost / Currency.objects.get(code=currency_code).rate_to_default,
                        Currency.get_default().code
                    ) for (cost, currency_code) in cost_by_backend
                )
            )
            for (backend_api_id, cost_by_backend) in costs_by_backend.items()
        )
    )
