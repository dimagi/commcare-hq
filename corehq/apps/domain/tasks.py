from celery.schedules import crontab
from celery.task import periodic_task

from django.conf import settings
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string

from corehq.apps.domain.views import EditBasicProjectInfoView
from corehq.apps.es.domains import DomainES
from corehq.apps.es.forms import FormES
from corehq.apps.users.models import WebUser

from dimagi.utils.django.email import send_HTML_email
from dimagi.utils.web import get_url_base


def _domains_over_x_forms(num_forms=200, domains=None):
    form_domains = FormES().domain_facet().size(0)
    if domains:
        form_domains = form_domains.domain(domains)
    form_domains = form_domains.run().facet('domain', 'terms')

    return {x['term'] for x in form_domains if x['count'] > num_forms}


def _real_incomplete_domains():
    incomplete_domains = (
        DomainES()
            .fields(["name"])
            .non_test_domains()
            .incomplete_domains()
            .run()
            .raw_hits
    )

    return {x['fields']['name'] for x in incomplete_domains}


def incomplete_domains_to_email():
    domains = _real_incomplete_domains()
    domains = _domains_over_x_forms(domains=list(domains))

    email_domains = []
    for domain in domains:
        users = list(WebUser.get_dimagi_emails_by_domain(domain))
        if users:
            email_domains.append(
                {
                    "domain_name": domain,
                    "email_to": users,
                    "settings_link": get_url_base() + reverse(
                        EditBasicProjectInfoView.urlname,
                        args=[domain]
                    )
                }
            )

    return email_domains


@periodic_task(
    run_every=crontab(minute=0, hour=0, day_of_week="monday", day_of_month="15-21"),
    queue='background_queue'
)
def fm_reminder_email():
    """
    Reminds FMs to update their domains with up to date information
    """
    email_domains = incomplete_domains_to_email()

    for domain in email_domains:
        email_content = render_to_string(
            'domain/email/fm_outreach.html', domain)
        email_content_plaintext = render_to_string(
            'domain/email/fm_outreach.txt', domain)
        send_HTML_email(
            "Please update your project settings for " + domain['domain_name'],
            domain['email_to'],
            email_content,
            email_from=settings.MASTER_LIST_EMAIL,
            text_content=email_content_plaintext,
            cc=[settings.MASTER_LIST_EMAIL],
        )


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


@periodic_task(
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
