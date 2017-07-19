import logging

from django.conf import settings
from django.template.loader import render_to_string
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Signature import PKCS1_PSS
from django.templatetags.i18n import language_name

from dimagi.utils.decorators.memoized import memoized
from corehq.apps.hqwebapp.forms import BulkUploadForm
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.users.models import WebUser
from custom.nic_compliance.utils import get_raw_password

logger = logging.getLogger(__name__)


@memoized
def get_hq_private_key():
    if settings.HQ_PRIVATE_KEY:
        return RSA.importKey(settings.HQ_PRIVATE_KEY)

    raise Exception('No private key found in localsettings.HQ_PRIVATE_KEY')


def sign(message):
    """
    Signs the SHA256 hash of message with HQ's private key, and returns
    the binary signature. The scheme used is RSASSA-PSS.
    """
    private_key = get_hq_private_key()
    sha256_hash = SHA256.new(message)
    signature = PKCS1_PSS.new(private_key).sign(sha256_hash)
    return signature


def send_confirmation_email(invitation):
    invited_user = invitation.email
    subject = '%s accepted your invitation to CommCare HQ' % invited_user
    recipient = WebUser.get_by_user_id(invitation.invited_by).get_email()
    context = {
        'invited_user': invited_user,
    }
    html_content = render_to_string('domain/email/invite_confirmation.html',
                                    context)
    text_content = render_to_string('domain/email/invite_confirmation.txt',
                                    context)
    send_html_email_async.delay(subject, recipient, html_content,
                                text_content=text_content)


def get_bulk_upload_form(context, context_key="bulk_upload"):
    return BulkUploadForm(
        context[context_key]['plural_noun'],
        context[context_key].get('action'),
        context_key + "_form"
    )


def csrf_inline(request):
    """
    Returns "<input type='hidden' name='csrfmiddlewaretoken' value='<csrf-token-value>' />",
    same as csrf_token template tag, but a shortcut without needing a Template or Context explicitly.

    Useful for adding inline forms in messages for e.g. while showing an "'undo' Archive Form" message
    """
    from django.template import Template, RequestContext
    node = "{% csrf_token %}"
    return Template(node).render(RequestContext(request))


def aliased_language_name(lang_code):
    """
    This is needed since we use non-standard language codes as alias, for e.g. 'fra' instead of 'fr' for French
    """
    try:
        return language_name(lang_code)
    except KeyError:
        for code, name in settings.LANGUAGES:
            if code == lang_code:
                return name
        raise KeyError('Unknown language code %s' % lang_code)


def decode_password(obfuscated_password, username=None):
    if settings.OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE:
        return get_raw_password(obfuscated_password, username)
    else:
        return obfuscated_password
