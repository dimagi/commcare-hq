import logging
import re
import base64
from datetime import datetime, timedelta

from django.conf import settings
from django.template.loader import render_to_string
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Signature import PKCS1_PSS
from django.templatetags.i18n import language_name

from dimagi.utils.decorators.memoized import memoized
from corehq.apps.hqwebapp.forms import BulkUploadForm
from corehq.apps.hqwebapp.models import HashedPasswordLoginAttempt
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.users.models import WebUser
from corehq.util.quickcache import quickcache

logger = logging.getLogger(__name__)
HASHED_PASSWORD_EXPIRY = 30  # days


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


def extract_password(password):
    # Passwords set with expected salts length and padding would respect this regex
    reg_exp = r"^sha256\$([a-z|0-9|A-Z]{6})(.*)([a-z|0-9|A-Z]{6})=$"
    match_result = re.match(reg_exp, password)
    # strip out outer level padding of salts/keys and ensure three matches
    if match_result and len(match_result.groups()) == 3:
        match_groups = re.match(reg_exp, password).groups()
        hash_left = match_groups[0]
        hash_right = match_groups[2]
        stripped_password = match_groups[1]
        # decode the stripped password to get internal block
        # decoded(salt1 + encoded_password + salt2)
        try:
            decoded_password = base64.b64decode(stripped_password)
        except TypeError:
            return ''
        match_result_2 = re.match(reg_exp, decoded_password)
        # strip out hashes from the internal block and ensure 3 matches
        if match_result_2 and len(match_result_2.groups()) == 3:
            match_groups = match_result_2.groups()
            # ensure the same hashes were used in the internal block as the outer
            if match_groups[0] == hash_left and match_groups[2] == hash_right:
                # decode to get the real password
                password_hash = re.match(reg_exp, decoded_password).groups()[1]
                # return password decoded for UTF-8 support
                try:
                    return base64.b64decode(password_hash).decode('utf-8')
                except TypeError:
                    return ''
            else:
                # this sounds like someone tried to hash something but failed so ignore the password submitted
                # completely
                return ''
        else:
            # this sounds like someone tried to hash something but failed so ignore the password submitted
            # completely
            return ''
    else:
        # return the password received AS-IS
        return password


# quickcache for multiple decode attempts in the same request:
# 1. an attempt to decode a password should be done just once in a request for the login attempt
# check to work correctly.
# 2. there should be no need to decode a password multiple times in the same request.
@quickcache(['password'], timeout=0)
def decode_password(password, username=None):
    if settings.ENABLE_PASSWORD_HASHING:
        if username:
            # To avoid replay attack where the same hash used for login is used on attack
            if HashedPasswordLoginAttempt.objects.filter(
                username=username,
                password_hash=password,
                used_at__gte=(datetime.today() - timedelta(HASHED_PASSWORD_EXPIRY))
            ).exists():
                return ''
            else:
                HashedPasswordLoginAttempt.objects.create(
                    username=username,
                    password_hash=password
                )
        return extract_password(password)
    return password
