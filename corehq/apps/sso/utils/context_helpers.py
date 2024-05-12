import datetime

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from corehq.const import USER_DATE_FORMAT
from dimagi.utils.web import get_site_domain


def render_multiple_to_strings(context, *templates):
    """
    Convenience utility that renders multiple templates with the same context.

    :param context: The context (dict) used to render all `*templates`.
    :param *templates: One or more template names (strings) to be rendered.
    :return: Generator of strings -- rendered text of each provided template.
    """
    return (render_to_string(template, context) for template in templates)


def get_idp_cert_expiration_email_context(idp):
    """
    Utility to generate metadata and render messages for an IdP certificate
    expiration reminder email.

    :param idp: IdentityProvider
    :return: Dict (parameters for sending email)
    """

    today = datetime.datetime.utcnow().date()
    exp_date = idp.date_idp_cert_expiration.date()
    num_days_left = (exp_date - today).days
    if num_days_left == 0:
        expires_on = _("today!")
    elif num_days_left == 1:
        expires_on = _("tomorrow!")
    else:
        expires_on = _(f"on {exp_date:{USER_DATE_FORMAT}}.")

    template_context = {
        "idp_name": idp.name,
        "expires_on": expires_on,
        "contact_email": settings.ACCOUNTS_EMAIL,
        "base_url": get_site_domain(),
    }
    subject = _(
        "CommCare Alert: Certificate for Identity Provider %(idp_name)s "
        "expires %(expires_on)s"
    ) % template_context
    body_html, body_txt = render_multiple_to_strings(
        template_context,
        "sso/email/idp_cert_expiring_reminder.html",
        "sso/email/idp_cert_expiring_reminder.txt",
    )
    email_context = {
        "subject": subject,
        "from": _(f"Dimagi CommCare Accounts <{settings.ACCOUNTS_EMAIL}>"),
        "to": idp.owner.enterprise_admin_emails,
        "bcc": [settings.ACCOUNTS_EMAIL],
        "html": body_html,
        "plaintext": body_txt,
    }
    if idp.owner.dimagi_contact:
        email_context["bcc"].append(idp.owner.dimagi_contact)
    return email_context


def get_graph_api_connection_issue_email_context(idp, error):
    subject = _("CommCare HQ Alert: SSO Remote User Management - Issue Connecting to Microsoft Graph API")
    template_context = {
        "error": error,
        "contact_email": settings.ACCOUNTS_EMAIL,
        "base_url": get_site_domain(),
    }
    body_html, body_txt = render_multiple_to_strings(
        template_context,
        "sso/email/microsoft_graph_api_connection_issue_notification.html",
        "sso/email/microsoft_graph_api_connection_issue_notification.txt",
    )
    email_context = {
        "subject": subject,
        "from": _(f"Dimagi CommCare Accounts <{settings.ACCOUNTS_EMAIL}>"),
        "to": idp.owner.enterprise_admin_emails or [idp.owner.dimagi_contact] or [settings.ACCOUNT_EMAIL],
        "bcc": [settings.ACCOUNTS_EMAIL],
        "html": body_html,
        "plaintext": body_txt,
    }
    if idp.owner.dimagi_contact:
        email_context["bcc"].append(idp.owner.dimagi_contact)
    return email_context


def get_sso_deactivation_skip_email_context(idp, failure_reason):
    subject = _("CommCare HQ Alert: Temporarily skipped automatic deactivation of SSO Web Users"
                " (Remote User Management)")
    template_context = {
        "contact_email": settings.ACCOUNTS_EMAIL,
        "base_url": get_site_domain(),
        "failure_reason": failure_reason,
    }
    body_html, body_txt = render_multiple_to_strings(
        template_context,
        "sso/email/sso_deactivation_skip_notification.html",
        "sso/email/sso_deactivation_skip_notification.txt",
    )
    email_context = {
        "subject": subject,
        "from": _(f"Dimagi CommCare Accounts <{settings.ACCOUNTS_EMAIL}>"),
        "to": idp.owner.enterprise_admin_emails or [idp.owner.dimagi_contact] or [settings.ACCOUNT_EMAIL],
        "bcc": [settings.ACCOUNTS_EMAIL],
        "html": body_html,
        "plaintext": body_txt,
    }
    if idp.owner.dimagi_contact:
        email_context["bcc"].append(idp.owner.dimagi_contact)
    return email_context


def get_api_secret_expiration_email_context(idp):
    """
    Utility to generate metadata and render messages for an IdP api secret
    expiration reminder email.

    :param idp: IdentityProvider
    :return: Dict (parameters for sending email)
    """

    today = datetime.datetime.utcnow().date()
    exp_date = idp.date_api_secret_expiration
    num_days_left = (exp_date - today).days
    if num_days_left == 0:
        expires_on = _("today!")
    elif num_days_left == 1:
        expires_on = _("tomorrow!")
    else:
        expires_on = _(f"on {exp_date:{USER_DATE_FORMAT}}.")

    template_context = {
        "idp_name": idp.name,
        "expires_on": expires_on,
        "contact_email": settings.ACCOUNTS_EMAIL,
        "base_url": get_site_domain(),
    }
    subject = _(
        "CommCare Alert: API Secret for Identity Provider %(idp_name)s "
        "expires %(expires_on)s"
    ) % template_context
    body_html, body_txt = render_multiple_to_strings(
        template_context,
        "sso/email/api_secret_expiring_reminder.html",
        "sso/email/api_secret_expiring_reminder.txt",
    )
    email_context = {
        "subject": subject,
        "from": _(f"Dimagi CommCare Accounts <{settings.ACCOUNTS_EMAIL}>"),
        "to": idp.owner.enterprise_admin_emails,
        "bcc": [settings.ACCOUNTS_EMAIL],
        "html": body_html,
        "plaintext": body_txt,
    }
    if idp.owner.dimagi_contact:
        email_context["bcc"].append(idp.owner.dimagi_contact)
    return email_context
