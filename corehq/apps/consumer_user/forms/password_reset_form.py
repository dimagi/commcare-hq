from captcha.fields import CaptchaField
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy

from corehq.apps.consumer_user.models import ConsumerUser
from corehq.apps.domain.forms import NoAutocompleteMixin
from corehq.apps.hqwebapp.tasks import send_html_email_async
from django.core.signing import Signer


class ConsumerUserPasswordResetForm(NoAutocompleteMixin, forms.Form):

    email = forms.EmailField(label=ugettext_lazy("Email"), max_length=254,
                             widget=forms.TextInput(attrs={'class': 'form-control'}))
    if settings.ADD_CAPTCHA_FIELD_TO_FORMS:
        captcha = CaptchaField(label=ugettext_lazy("Type the letters in the box"))
    error_messages = {
        'unknown': ugettext_lazy("That email address doesn't have an associated user account. Are you sure you've "
                                 "registered?"),
        'unusable': ugettext_lazy("The user account associated with this email address cannot reset the "
                                  "password."),
    }

    def clean_email(self):
        UserModel = get_user_model()
        email = Signer().sign(self.cleaned_data["email"])
        matching_users = UserModel._default_manager.filter(username__iexact=email)

        # below here is not modified from the superclass
        if not len(matching_users):
            raise forms.ValidationError(self.error_messages['unknown'])
        if not any(user.is_active for user in matching_users):
            # none of the filtered users are active
            raise forms.ValidationError(self.error_messages['unknown'])
        if any((user.password == UNUSABLE_PASSWORD_PREFIX)
               for user in matching_users):
            raise forms.ValidationError(self.error_messages['unusable'])
        return email

    def save(self, domain_override=None,
             subject_template_name='registration/password_reset_subject.txt',
             email_template_name='registration/password_reset_email.html',
             # WARNING: Django 1.7 passes this in automatically. do not remove
             html_email_template_name=None,
             use_https=False, token_generator=default_token_generator,
             from_email=None, request=None, **kwargs):
        """
        Generates a one-use only link for resetting password and sends to the
        user.
        """

        if settings.IS_SAAS_ENVIRONMENT:
            subject_template_name = 'registration/email/password_reset_subject_hq.txt'
            email_template_name = 'registration/email/password_reset_email_hq.html'

        email = self.cleaned_data["email"]

        user = User.objects.get(username=email)

        consumer_user = ConsumerUser.objects.get(user=user)
        print(consumer_user)

        if consumer_user and user.has_usable_password():
            if not domain_override:
                current_site = get_current_site(request)
                site_name = current_site.name
                domain = current_site.domain
            else:
                site_name = domain = domain_override

            user_email = user.email

            c = {
                'email': user_email,
                'domain': domain,
                'site_name': site_name,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'user': user,
                'token': token_generator.make_token(user),
                'protocol': 'https' if use_https else 'http',
            }
            print(c)
            subject = render_to_string(subject_template_name, c)
            # Email subject *must not* contain newlines
            subject = ''.join(subject.splitlines())

            message_plaintext = render_to_string('registration/password_reset_email.html', c)
            message_html = render_to_string(email_template_name, c)

            send_html_email_async.delay(
                subject, user_email, message_html,
                text_content=message_plaintext,
                email_from=settings.DEFAULT_FROM_EMAIL
            )


class ConfidentialPasswordResetForm(ConsumerUserPasswordResetForm):

    def clean_email(self):
        try:
            return super(ConfidentialPasswordResetForm, self).clean_email()
        except forms.ValidationError:
            # The base class throws various emails that give away information about the user;
            # we can pretend all is well since the save() method is safe for missing users.
            return self.cleaned_data['email']


class ConsumerUserSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(label=ugettext_lazy("New password"), widget=forms.PasswordInput(
        attrs={'data-bind': "value: password, valueUpdate: 'input'"}),
        help_text=mark_safe("""<span data-bind="text: passwordHelp, css: color">"""))

    def save(self, commit=True):
        user = super(ConsumerUserSetPasswordForm, self).save(commit)
        return user
