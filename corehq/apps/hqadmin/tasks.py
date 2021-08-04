import csv
import io
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connections
from django.db.models import Q
from django.template import Context, Template
from django.template.loader import render_to_string

import attr
from celery.schedules import crontab
from celery.task import task
from celery.task.base import periodic_task

from dimagi.utils.django.email import send_HTML_email
from dimagi.utils.logging import notify_error
from dimagi.utils.web import get_static_url_prefix
from pillowtop.utils import get_couch_pillow_instances

from corehq.apps.es.users import UserES
from corehq.apps.hqadmin.models import HistoricalPillowCheckpoint
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.elastic import get_es_new
from corehq.util.celery_utils import periodic_task_when_true
from corehq.util.metrics import metrics_gauge
from corehq.util.soft_assert import soft_assert

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


@periodic_task_when_true(settings.IS_DIMAGI_ENVIRONMENT, run_every=crontab(minute=0),
                         queue='background_queue')
def check_non_dimagi_superusers():
    non_dimagis_superuser = ', '.join((get_user_model().objects.filter(
        (Q(is_staff=True) | Q(is_superuser=True)) & ~Q(username__endswith='@dimagi.com')
    ).values_list('username', flat=True)))
    if non_dimagis_superuser:
        message = "{non_dimagis} have superuser privileges".format(non_dimagis=non_dimagis_superuser)
        _soft_assert_superusers(False, message)
        notify_error(message=message)


@task(serializer='pickle', queue="email_queue")
def send_mass_emails(username, real_email, subject, html, text):
    if real_email:
        recipients = [{
            'username': h['username'],
            'first_name': h['first_name'] or 'CommCare User',
        } for h in UserES().web_users().run().hits]
    else:
        recipients = [{
            'username': username,
            'first_name': 'CommCare User',
        }]

    successes = []
    failures = []
    for recipient in recipients:
        context = recipient
        context.update({
            'url_prefix': get_static_url_prefix()
        })

        html_template = Template(html)
        text_template = Template(text)
        text_content = render_to_string("hqadmin/email/mass_email_base.txt", {
            'email_body': text_template.render(Context(context)),
        })
        html_content = render_to_string("hqadmin/email/mass_email_base.html", {
            'email_body': html_template.render(Context(context)),
        })

        try:
            send_HTML_email(subject, recipient['username'], html_content, text_content=text_content)
            successes.append((recipient['username'], None))
        except Exception as e:
            failures.append((recipient['username'], e))

    message = (
        "Subject: {subject},\n"
        "Total successes: {success_count} \n Total errors: {failure_count} \n"
        "".format(
            subject=subject,
            success_count=len(successes),
            failure_count=len(failures))
    )

    send_html_email_async(
        "Mass email summary", username, message,
        text_content=message, file_attachments=[
            _mass_email_attachment('successes', successes),
            _mass_email_attachment('failures', failures)]
    )


@attr.s
class AbnormalUsageAlert(object):
    source = attr.ib()
    domain = attr.ib()
    message = attr.ib()


@task(serializer='pickle', queue="email_queue")
def send_abnormal_usage_alert(alert):
    """ Sends an alert to #support and email to let support know when a domain is doing something weird

    :param alert: AbnormalUsageAlert object
    """

    subject = "{domain} is doing something interesting with the {source} in the {environment} env".format(
        domain=alert.domain,
        source=alert.source,
        environment=settings.SERVER_ENVIRONMENT
    )
    send_html_email_async(
        subject,
        settings.SUPPORT_EMAIL,
        alert.message
    )


def _mass_email_attachment(name, rows):
    csv_file = io.StringIO()
    writer = csv.writer(csv_file)
    writer.writerow(['Email', 'Error'])
    writer.writerows(rows)
    attachment = {
        'title': "mass_email_{}.csv".format(name),
        'mimetype': 'text/csv',
        'file_obj': csv_file,
    }
    return attachment


@periodic_task_when_true(settings.IS_SAAS_ENVIRONMENT, run_every=crontab(minute="0", hour="*/4"),
                         queue='background_queue')
def cleanup_stale_es_on_couch_domains_task():
    from corehq.apps.hqadmin.couch_domain_utils import cleanup_stale_es_on_couch_domains
    cleanup_stale_es_on_couch_domains()


@periodic_task(queue='background_queue', run_every=crontab(minute="*/5"))
def track_es_doc_counts():
    es = get_es_new()
    stats = es.indices.stats(level='shards', metric='docs')
    for name, data in stats['indices'].items():
        for number, shard in data['shards'].items():
            for i in shard:
                if i['routing']['primary']:
                    tags = {
                        'index': name,
                        'shard': f'{name}_{number}',
                    }
                    metrics_gauge('elasticsearch.shards.docs.count', i['docs']['count'], tags)
                    metrics_gauge('elasticsearch.shards.docs.deleted', i['docs']['deleted'], tags)


@periodic_task(queue='background_queue', run_every=crontab(minute="0", hour="0"))
def track_pg_limits():
    for db in settings.DATABASES:
        with connections[db].cursor() as cursor:
            query = """
            select tab.relname, seq.relname
              from pg_class seq
              join pg_depend as dep on seq.oid=dep.objid
              join pg_class as tab on dep.refobjid = tab.oid
              join pg_attribute as att on att.attrelid=tab.oid and att.attnum=dep.refobjsubid
              where seq.relkind='S' and att.attlen=4
            """
            cursor.execute(query)
            results = cursor.fetchall()
            for table, sequence in results:
                cursor.execute(f'select last_value from {sequence}')
                current_value = cursor.fetchone()[0]
                metrics_gauge('postgres.sequence.current_value', current_value, {'table': table, 'database': db})
