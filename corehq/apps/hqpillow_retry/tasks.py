from datetime import datetime, timedelta
from celery.schedules import crontab
from celery.task.base import periodic_task
from django.core.mail import mail_admins
from django.core.urlresolvers import reverse
from django.db.models.aggregates import Count
from django.template.loader import render_to_string
from dimagi.utils.web import get_url_base
from pillow_retry.models import PillowError
from django.conf import settings


@periodic_task(run_every=crontab(minute=0), queue='background_queue')
def pillow_retry_notifier():
    enddate = datetime.utcnow()
    startdate = enddate - timedelta(hours=1)
    results = PillowError.objects \
        .filter(date_last_attempt__gte=startdate) \
        .filter(current_attempt__gte=settings.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS) \
        .values_list('pillow', 'error_type') \
        .annotate(Count('pillow')) \
        .order_by('-pillow__count').all()

    if results:
        results = list(results)
        text_rows = format_text_table([('Pillow', 'Error', 'Count')] + results)
        context = {
            'startdate': startdate,
            'enddate': enddate,
            'rows': text_rows,
            'url': get_url_base() + reverse('admin_report_dispatcher', args=('pillow_errors',))
        }
        text_message = render_to_string('hqpillow_retry/email.txt', context)
        context['rows'] = results
        html_message = render_to_string('hqpillow_retry/email.html', context)
        mail_admins('PillowTop errors in the last hour', text_message, html_message=html_message)


def format_text_table(table):
    col_width = [max(len(str(x)) for x in col) for col in zip(*table)]
    output = []
    for row in table:
        inner = " | ".join("{0:{1}}".format(x, col_width[i]) for i, x in enumerate(row))
        output.append("| {0} |".format(inner))

    return output
