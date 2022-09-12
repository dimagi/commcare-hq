from django.contrib import messages
from django.utils.translation import gettext as _
from django.utils.html import format_html


def get_success_message_for_trusted_idp(idp, domain_obj):
    """
    Small utility to return a success message that a TrustedIdentityProvider
    relationship was established between an Identity Provider and a Domain.

    :param idp: IdentityProvider
    :param domain_obj: Domain object
    :return: String (the final message)
    """
    return format_html(
        _('{idp} is now trusted as an identity provider for users '
          'who are members of the project space "{domain}". '
          '<a href="{learn_more}">Learn More</a>'),
        idp=idp.name,
        domain=domain_obj.name,
        learn_more='#',  # todo include learn more link
    )


def show_sso_login_success_or_error_messages(request):
    """Displays any success or error messages after authenticating a user through the SsoBackend.

    We add the messages to the django messages framework here since
    that middleware was not available for SsoBackend"""
    if hasattr(request, 'sso_new_user_messages'):
        for success_message in request.sso_new_user_messages['success']:
            messages.success(request, success_message)
        for error_message in request.sso_new_user_messages['error']:
            messages.error(request, error_message)
