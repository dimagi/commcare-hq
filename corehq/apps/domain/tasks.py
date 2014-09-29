from celery.schedules import crontab
from celery.task import periodic_task, task

from django.template.loader import render_to_string

from corehq.apps.es.domains import DomainES
from corehq.apps.es.forms import FormES
from corehq.apps.users.models import WebUser

from dimagi.utils.django.email import send_HTML_email
from dimagi.utils.web import get_url_base


def _domains_over_x_forms(num_forms=200):
    form_domains = (
            FormES()
            .domain_facet()
            .run()
            .facet('domain', 'terms')
    )
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


def domains_to_email():
    domains = _real_incomplete_domains() & _domains_over_x_forms()

    email_domains = []
    for domain in domains:
        users = list(WebUser.get_dimagi_emails_by_domain(domain))
        if len(users) > 0:
            email_domains.append(
                {
                    "domain_name": domain,
                    "email_to": users,
                    "settings_link": get_url_base()
                }
            )

    return email_domains


@periodic_task(run_every=crontab(minute=0, hour=0, day_of_week="sunday"))
def fm_reminder_email():
    """
    Reminds FMs to update their domains with up to date information
    """
    email_domains = domains_to_email()

    for domain in email_domains:
        email_content = render_to_string(
                'domain/email/fm_outreach.html', domain)
        email_content_plaintext = render_to_string(
                'domain/email/fm_outreach.txt', domain)
        for email in domain['email_to']:
            send_HTML_email(
                "Please update your domain",
                email,
                email_content,
                email_from="master-list@dimagi.com",
                text_content=email_content_plaintext,
                cc=["master-list@dimagi.com"],
            )
