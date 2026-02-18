from datetime import datetime

from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override

from dimagi.utils.web import get_static_url_prefix

from corehq.apps.domain.utils import (
    encrypt_account_confirmation_info,
    guess_domain_language_for_sms,
)
from corehq.apps.registration.utils import project_logo_emails_context
from corehq.util.view_utils import absolute_reverse


def send_account_confirmation_if_necessary(couch_user):
    """
    Sends an account confirmation email if necessary (user has just signed up
    and is in an unconfirmed state).

    Returns whether an email was sent or not.
    :param couch_user:
    :return:
    """
    if should_send_account_confirmation(couch_user):
        send_account_confirmation(couch_user)
        return True
    else:
        return False


def should_send_account_confirmation(couch_user):
    if not couch_user.is_commcare_user():
        return False
    # todo: this might want to get more complex, e.g. maintain state of whether it has been
    # sent already, etc.
    return not couch_user.is_account_confirmed


def send_account_confirmation(commcare_user):
    from corehq.apps.hqwebapp.tasks import send_html_email_async
    from corehq.apps.users.views.mobile import (
        CommCareUserConfirmAccountViewByEmailView,
    )
    encrypted_user_info = encrypt_account_confirmation_info(commcare_user)
    template_params = _get_account_confirmation_template_params(
        commcare_user, encrypted_user_info, CommCareUserConfirmAccountViewByEmailView.urlname
    )
    template_params.update(project_logo_emails_context(commcare_user.domain))

    lang = guess_domain_language_for_sms(commcare_user.domain)
    with override(lang):
        text_content = render_to_string("registration/email/mobile_worker_confirm_account.txt",
                                        template_params)
        html_content = render_to_string("registration/email/mobile_worker_confirm_account.html",
                                        template_params)
        subject = _(f'Confirm your CommCare account for {commcare_user.domain}')
    commcare_user.confirmation_sent_at = datetime.utcnow()
    commcare_user.save()
    send_html_email_async.delay(subject, commcare_user.email, html_content,
                                text_content=text_content,
                                domain=commcare_user.domain,
                                use_domain_gateway=True)


def _get_account_confirmation_template_params(commcare_user, message_token, url_name):
    url = absolute_reverse(url_name, args=[commcare_user.domain, message_token])
    return {
        'name': commcare_user.full_name,
        'domain': commcare_user.domain,
        'username': commcare_user.raw_username,
        'url': url,
        'url_prefix': get_static_url_prefix(),
        'hq_name': 'CommCare HQ',
    }
