from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import date, timedelta

import io

from celery.schedules import crontab
from celery import group
from celery.task import task
from celery.task.base import periodic_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.template import Context, Template
from django.template.loader import render_to_string

from corehq.apps.hqadmin.models import HistoricalPillowCheckpoint
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.util.soft_assert import soft_assert
from dimagi.utils.csv import UnicodeWriter
from dimagi.utils.logging import notify_error
from dimagi.utils.django.email import send_HTML_email
from dimagi.utils.web import get_site_domain
from pillowtop.utils import get_couch_pillow_instances
from .utils import check_for_rewind

_soft_assert_superusers = soft_assert(notify_admins=True)


@periodic_task(run_every=crontab(hour=0, minute=0), queue='background_queue')
def check_pillows_for_rewind():
    for pillow in get_couch_pillow_instances():
        checkpoint = pillow.checkpoint
        has_rewound, historical_seq = check_for_rewind(checkpoint)
        if has_rewound:
            notify_error(
                message='Found seq number lower than previous for {}. '
                        'This could mean we are in a rewind state'.format(checkpoint.checkpoint_id),
                details={
                    'pillow checkpoint seq': checkpoint.get_current_sequence_id(),
                    'stored seq': historical_seq
                }
            )


@periodic_task(run_every=crontab(hour=0, minute=0), queue='background_queue')
def create_historical_checkpoints():
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    HistoricalPillowCheckpoint.create_pillow_checkpoint_snapshots()
    HistoricalPillowCheckpoint.objects.filter(date_updated__lt=thirty_days_ago).delete()


@periodic_task(run_every=crontab(minute=0), queue='background_queue')
def check_non_dimagi_superusers():
    non_dimagis_superuser = ', '.join((get_user_model().objects.filter(
        (Q(is_staff=True) | Q(is_superuser=True)) & ~Q(username__endswith='@dimagi.com')
    ).values_list('username', flat=True)))
    if non_dimagis_superuser:
        _soft_assert_superusers(
            False, "{non_dimagis} have superuser privileges".format(non_dimagis=non_dimagis_superuser))


@task(queue="email_queue", bind=True, acks_late=True)
def send_mass_emails(self, couch_user, recipients, subject, html, text):
    tasks = []
    for recipient in recipients:
        context = recipient
        context.update({
            'url_prefix': '' if settings.STATIC_CDN else 'http://' + get_site_domain(),
        })

        html_template = Template(html)
        text_template = Template(text)
        text_content = render_to_string("hqadmin/email/mass_email_base.txt", {
            'email_body': text_template.render(Context(context)),
        })
        html_content = render_to_string("hqadmin/email/mass_email_base.html", {
            'email_body': html_template.render(Context(context)),
        })

        tasks.append(send_single_mass_email.s(subject, recipient['username'],
                        html_content, text_content, email_from=settings.DEFAULT_FROM_EMAIL))

    result = group(tasks)().get()
    successes = [email for (email, error) in result if not error]
    failures = [(email, error) for (email, error) in result if error]

    if len(failures):
        subject = "Mass email failures"
        csv_file = io.BytesIO()
        writer = UnicodeWriter(csv_file)
        writer.writerow(['Email', 'Error'])
        writer.writerows(failures)

        message = (
            "Subject: {subject},\n"
            "Total successes: {success_count} \n Total errors: {failure_count} \n"
            "".format(
                subject=subject,
                success_count=len(successes),
                failure_count=len(failures))
        )

        attachment = {
            'title': "mass_email_failures.csv",
            'mimetype': 'text/csv',
            'file_obj': csv_file,
        }
        send_html_email_async(
            subject, couch_user.username, message,
            text_content=message, file_attachments=[attachment]
        )


@task(queue="email_queue",
      bind=True, default_retry_delay=15 * 60, max_retries=10, acks_late=True)
def send_single_mass_email(self, subject, recipient, html_content,
                          text_content=None, cc=None,
                          email_from=settings.DEFAULT_FROM_EMAIL,
                          file_attachments=None, bcc=None):
    '''
    Returns tuple of (email, Exception) where Exception is None if the mail succeeded
    Skips send_html_email_async's retry logic in favor of notifying on all failures.
    '''
    try:
        import re
        if not re.search(r'@', recipient):
            raise Exception("nope no email")
        send_HTML_email(subject, recipient, html_content,
                        text_content=text_content, cc=cc, email_from=email_from,
                        file_attachments=file_attachments, bcc=bcc)
        return (recipient, None)
    except Exception as e:
        return (recipient, e)
