from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import override, ugettext_lazy as _

from corehq.apps.domain.utils import guess_domain_language
from corehq.util.context_processors import commcare_hq_names
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.web import get_static_url_prefix


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
    from corehq.apps.users.models import CommCareUser
    if not isinstance(couch_user, CommCareUser):
        return False
    # todo: this might want to get more complex, e.g. maintain state of whether it has been
    # sent already, etc.
    return not couch_user.is_account_confirmed


def send_account_confirmation(commcare_user):
    from corehq.apps.hqwebapp.tasks import send_html_email_async
    from corehq.apps.users.views.mobile import CommCareUserConfirmAccountView
    url = absolute_reverse(CommCareUserConfirmAccountView.urlname,
                           args=[commcare_user.domain, commcare_user.get_id])
    template_params = {
        'domain': commcare_user.domain,
        'username': commcare_user.raw_username,
        'url': url,
        'url_prefix': get_static_url_prefix(),
        'hq_name': commcare_hq_names()['commcare_hq_names']['COMMCARE_HQ_NAME']
    }

    lang = guess_domain_language(commcare_user.domain)
    with override(lang):
        text_content = render_to_string("registration/email/mobile_worker_confirm_account.txt",
                                        template_params)
        html_content = render_to_string("registration/email/mobile_worker_confirm_account.html",
                                        template_params)
        subject = _(f'Confirm your CommCare account for {commcare_user.domain}')
    send_html_email_async.delay(subject, commcare_user.email, html_content,
                                text_content=text_content,
                                email_from=settings.DEFAULT_FROM_EMAIL)
