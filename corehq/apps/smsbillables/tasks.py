from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import date

from celery.schedules import crontab
from celery.task import periodic_task

from django.conf import settings

from corehq.apps.smsbillables.models import (
    SmsBillable,
    SmsGatewayFeeCriteria,
)
from corehq.util.log import send_HTML_email
from dimagi.utils.dates import add_months_to_date


@periodic_task(run_every=crontab(day_of_month='1', hour=13, minute=0), queue='background_queue', acks_late=True)
def send_gateway_fee_report_out():
    backend_api_ids = SmsGatewayFeeCriteria.objects.values_list('backend_api_id', flat=True).distinct()
    first_day_previous_month = add_months_to_date(date.today(), -1)
    billables_in_month = SmsBillable.objects.filter(
        date_sent__year=first_day_previous_month.year,
        date_sent__month=first_day_previous_month.month,
        is_valid=True,
    )
    cost_by_backend = {
        backend_api_id: sum(billable.gateway_charge for billable in
            billables_in_month.filter(gateway_fee__criteria__backend_api_id=backend_api_id))
        for backend_api_id in backend_api_ids
    }

    subject = "[{}] Cost per SMS Gateway Monthly Summary".format(settings.SERVER_ENVIRONMENT)

    send_HTML_email(
        subject,
        settings.ACCOUNTS_EMAIL,
        ''.join('<p>{}: {}</p>'.format(backend, cost) for (backend, cost) in cost_by_backend.items())
        + '<p>All values in USD</p>'
    )
