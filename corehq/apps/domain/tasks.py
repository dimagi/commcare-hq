from django.conf import settings
from django.template.loader import render_to_string

from celery.schedules import crontab

from corehq.apps.celery import periodic_task_when_true
from corehq.apps.es.domains import DomainES
from corehq.apps.es.forms import FormES
from corehq.apps.users.models import WebUser
from corehq.util.log import send_HTML_email


def _domains_over_x_forms(num_forms=200, domains=None):
    form_domains = FormES().domain_aggregation().size(0)
    if domains:
        form_domains = form_domains.domain(domains)
    form_domains = form_domains.run().aggregations.domain.buckets_list

    return {x.key for x in form_domains if x.doc_count > num_forms}


def _real_incomplete_domains():
    incomplete_domains = (
        DomainES()
            .fields(["name"])
            .non_test_domains()
            .incomplete_domains()
            .run()
            .hits
    )

    return {x['name'] for x in incomplete_domains}


def incomplete_self_started_domains():
    """
    Returns domains that have submitted 200 forms, but haven't filled out any
    project information
    """
    domains = _real_incomplete_domains()
    domains = _domains_over_x_forms(domains=list(domains))

    email_domains = []
    for domain in domains:
        users = list(WebUser.get_dimagi_emails_by_domain(domain))
        if not users:
            email_domains.append(domain)

    return email_domains


@periodic_task_when_true(
    settings.IS_SAAS_ENVIRONMENT,
    run_every=crontab(minute=0, hour=0, day_of_week="monday", day_of_month="15-21"),
    queue='background_queue',
)
def self_starter_email():
    """
    Emails MASTER_LIST_EMAIL incomplete self started domains

    Doesn't actually look at self-started attribute.
    """
    domains = incomplete_self_started_domains()

    if len(domains) > 0:
        email_content = render_to_string(
            'domain/email/self_starter.html', {'domains': domains})
        email_content_plaintext = render_to_string(
            'domain/email/self_starter.txt', {'domains': domains})
        send_HTML_email(
            "Incomplete Self Started Domains",
            settings.MASTER_LIST_EMAIL,
            email_content,
            text_content=email_content_plaintext,
        )
