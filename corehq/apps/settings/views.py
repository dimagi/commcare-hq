from __future__ import absolute_import, unicode_literals

import json
import re
from base64 import b64encode
from io import BytesIO

import qrcode
import six
from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy, ugettext_noop
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST
from memoized import memoized
from tastypie.models import ApiKey
from two_factor.models import PhoneDevice
from two_factor.utils import default_device
from two_factor.views import (
    BackupTokensView,
    DisableView,
    PhoneDeleteView,
    PhoneSetupView,
    ProfileView,
    SetupCompleteView,
    SetupView,
)

import langcodes
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    login_required,
    require_superuser,
    two_factor_exempt,
)
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.utils import sign, update_session_language
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.settings.forms import (
    HQDeviceValidationForm,
    HQEmptyForm,
    HQPasswordChangeForm,
    HQPhoneNumberForm,
    HQPhoneNumberMethodForm,
    HQTOTPDeviceForm,
    HQTwoFactorMethodForm,
)
from corehq.apps.users.forms import AddPhoneNumberForm
from corehq.mobile_flags import ADVANCED_SETTINGS_ACCESS, MULTIPLE_APPS_UNLIMITED
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.quickcache import quickcache
from dimagi.utils.couch import CriticalSection
from dimagi.utils.web import json_response


@login_and_domain_required
def default(request, domain):
    return HttpResponseRedirect(reverse("users_default", args=[domain]))


@login_and_domain_required
def redirect_users(request, domain, old_url=""):
    return HttpResponseRedirect(reverse("users_default", args=[domain]))


@login_and_domain_required
def redirect_domain_settings(request, domain, old_url=""):
    return HttpResponseRedirect(reverse("domain_forwarding", args=[domain]))


@require_superuser
def project_id_mapping(request, domain):
    from corehq.apps.users.models import CommCareUser
    from corehq.apps.groups.models import Group

    users = CommCareUser.by_domain(domain)
    groups = Group.by_domain(domain)

    return json_response({
        'users': dict([(user.raw_username, user.user_id) for user in users]),
        'groups': dict([(group.name, group.get_id) for group in groups]),
    })


class BaseMyAccountView(BaseSectionPageView):
    section_name = ugettext_lazy("My Account")

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(BaseMyAccountView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def main_context(self):
        context = super(BaseMyAccountView, self).main_context
        context.update({
            'is_my_account_settings': True,
        })
        return context

    @property
    def section_url(self):
        return reverse(MyAccountSettingsView.urlname)


class DefaultMySettingsView(BaseMyAccountView):
    urlname = "default_my_settings"

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse(MyAccountSettingsView.urlname))


class MyAccountSettingsView(BaseMyAccountView):
    urlname = 'my_account_settings'
    page_title = ugettext_lazy("My Information")
    api_key = None
    template_name = 'settings/edit_my_account.html'

    @two_factor_exempt
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(MyAccountSettingsView, self).dispatch(request, *args, **kwargs)

    def get_or_create_api_key(self):
        if not self.api_key:
            with CriticalSection(['get-or-create-api-key-for-%d' % self.request.user.id]):
                api_key, _ = ApiKey.objects.get_or_create(user=self.request.user)
            self.api_key = api_key.key
        return self.api_key

    @property
    @memoized
    def settings_form(self):
        language_choices = langcodes.get_all_langs_for_select()
        api_key = self.get_or_create_api_key()
        from corehq.apps.users.forms import UpdateMyAccountInfoForm
        try:
            domain = self.request.domain
        except AttributeError:
            domain = ''
        if self.request.method == 'POST':
            form = UpdateMyAccountInfoForm(
                self.request.POST,
                api_key=api_key,
                domain=domain,
                existing_user=self.request.couch_user,
            )
        else:
            form = UpdateMyAccountInfoForm(
                api_key=api_key,
                domain=domain,
                existing_user=self.request.couch_user,
            )
        form.load_language(language_choices)
        return form

    @property
    def page_context(self):
        user = self.request.couch_user
        return {
            'form': self.settings_form,
            'add_phone_number_form': AddPhoneNumberForm(),
            'api_key': self.get_or_create_api_key(),
            'phonenumbers': user.phone_numbers_extended(user),
            'user_type': 'mobile' if user.is_commcare_user() else 'web',
        }

    def phone_number_is_valid(self):
        if isinstance(self.phone_number, six.string_types):
            soft_assert_type_text(self.phone_number)
        return (
            isinstance(self.phone_number, six.string_types) and
            re.compile(r'^\d+$').match(self.phone_number) is not None
        )

    def process_add_phone_number(self):
        if self.phone_number_is_valid():
            user = self.request.couch_user
            user.add_phone_number(self.phone_number)
            user.save()
            messages.success(self.request, _("Phone number added."))
        else:
            messages.error(self.request, _("Invalid phone number format entered. "
                "Please enter number, including country code, in digits only."))
        return HttpResponseRedirect(reverse(MyAccountSettingsView.urlname))

    def process_delete_phone_number(self):
        self.request.couch_user.delete_phone_number(self.phone_number)
        messages.success(self.request, _("Phone number deleted."))
        return HttpResponseRedirect(reverse(MyAccountSettingsView.urlname))

    def process_make_phone_number_default(self):
        self.request.couch_user.set_default_phone_number(self.phone_number)
        messages.success(self.request, _("Primary phone number updated."))
        return HttpResponseRedirect(reverse(MyAccountSettingsView.urlname))

    @property
    @memoized
    def phone_number(self):
        return self.request.POST.get('phone_number')

    @property
    @memoized
    def form_actions(self):
        return {
            'add-phonenumber': self.process_add_phone_number,
            'delete-phone-number': self.process_delete_phone_number,
            'make-phone-number-default': self.process_make_phone_number_default,
        }

    @property
    @memoized
    def form_type(self):
        return self.request.POST.get('form_type')

    def post(self, request, *args, **kwargs):
        if self.form_type and self.form_type in self.form_actions:
            return self.form_actions[self.form_type]()
        if self.settings_form.is_valid():
            old_lang = self.request.couch_user.language
            self.settings_form.update_user()
            new_lang = self.request.couch_user.language
            update_session_language(request, old_lang, new_lang)

        return self.get(request, *args, **kwargs)


class MyProjectsList(BaseMyAccountView):
    urlname = 'my_projects'
    page_title = ugettext_lazy("My Projects")
    template_name = 'settings/my_projects.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.couch_user.is_web_user():
            raise Http404

        return super(MyProjectsList, self).dispatch(request, *args, **kwargs)

    @property
    def all_domains(self):
        all_domains = self.request.couch_user.get_domains()
        for d in all_domains:
            yield {
                'name': d,
                'is_admin': self.request.couch_user.is_domain_admin(d)
            }

    @property
    def page_context(self):
        return {
            'domains': self.all_domains,
            'web_user': self.request.couch_user.is_web_user
        }

    @property
    @memoized
    def domain_to_remove(self):
        if self.request.method == 'POST':
            return self.request.POST['domain']

    def post(self, request, *args, **kwargs):
        if self.request.couch_user.is_domain_admin(self.domain_to_remove):
            messages.error(request, _("Unable remove membership because you are the admin of %s")
                                    % self.domain_to_remove)
        else:
            try:
                self.request.couch_user.delete_domain_membership(self.domain_to_remove, create_record=True)
                self.request.couch_user.save()
                messages.success(request, _("You are no longer part of the project %s") % self.domain_to_remove)
            except Exception:
                messages.error(request, _("There was an error removing you from this project."))
        return self.get(request, *args, **kwargs)


class ChangeMyPasswordView(BaseMyAccountView):
    urlname = 'change_my_password'
    template_name = 'settings/change_my_password.html'
    page_title = ugettext_lazy("Change My Password")

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(ChangeMyPasswordView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def password_change_form(self):
        if self.request.method == 'POST':
            return HQPasswordChangeForm(user=self.request.user, data=self.request.POST)
        return HQPasswordChangeForm(user=self.request.user)

    @property
    def page_context(self):
        return {
            'form': self.password_change_form,
            'hide_password_feedback': settings.ENABLE_DRACONIAN_SECURITY_FEATURES,
            'implement_password_obfuscation': settings.OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE,
        }

    @method_decorator(sensitive_post_parameters())
    def post(self, request, *args, **kwargs):
        if self.password_change_form.is_valid():
            self.password_change_form.save()
            messages.success(request, _("Your password was successfully changed!"))
        return self.get(request, *args, **kwargs)


class TwoFactorProfileView(BaseMyAccountView, ProfileView):
    urlname = 'two_factor_settings'
    template_name = 'two_factor/profile/profile.html'
    page_title = ugettext_lazy("Two Factor Authentication")

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(TwoFactorProfileView, self).dispatch(request, *args, **kwargs)


class TwoFactorSetupView(BaseMyAccountView, SetupView):
    urlname = 'two_factor_setup'
    template_name = 'two_factor/core/setup.html'
    page_title = ugettext_lazy("Two Factor Authentication Setup")

    form_list = (
        ('welcome_setup', HQEmptyForm),
        ('method', HQTwoFactorMethodForm),
        ('generator', HQTOTPDeviceForm),
        ('sms', HQPhoneNumberForm),
        ('call', HQPhoneNumberForm),
        ('validation', HQDeviceValidationForm),
    )

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(TwoFactorSetupView, self).dispatch(request, *args, **kwargs)


class TwoFactorSetupCompleteView(BaseMyAccountView, SetupCompleteView):
    urlname = 'two_factor_setup_complete'
    template_name = 'two_factor/core/setup_complete.html'
    page_title = ugettext_lazy("Two Factor Authentication Setup Complete")

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(TwoFactorSetupCompleteView, self).dispatch(request, *args, **kwargs)


class TwoFactorBackupTokensView(BaseMyAccountView, BackupTokensView):
    urlname = 'two_factor_backup_tokens'
    template_name = 'two_factor/core/backup_tokens.html'
    page_title = ugettext_lazy("Two Factor Authentication Backup Tokens")

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(TwoFactorBackupTokensView, self).dispatch(request, *args, **kwargs)


class TwoFactorDisableView(BaseMyAccountView, DisableView):
    urlname = 'two_factor_disable'
    template_name = 'two_factor/profile/disable.html'
    page_title = ugettext_lazy("Disable Two Factor Authentication")

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(TwoFactorDisableView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return DisableView.get(self, request, *args, **kwargs)


class TwoFactorPhoneSetupView(BaseMyAccountView, PhoneSetupView):
    urlname = 'two_factor_phone_setup'
    template_name = 'two_factor/core/phone_register.html'
    page_title = ugettext_lazy("Two Factor Authentication Phone Setup")

    form_list = (
        ('method', HQPhoneNumberMethodForm),
        ('validation', HQDeviceValidationForm),
    )

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(TwoFactorPhoneSetupView, self).dispatch(request, *args, **kwargs)

    def done(self, form_list, **kwargs):
        """
        Store the device and reload the page.
        """
        self.get_device(user=self.request.user, name='backup').save()
        messages.add_message(self.request, messages.SUCCESS, _("Phone number added."))
        return redirect(reverse(TwoFactorProfileView.urlname))

    def get_device(self, **kwargs):
        """
        Uses the data from the setup step and generated key to recreate device, gets the 'method' step
        in the form_list.
        """
        kwargs = kwargs or {}
        kwargs.update(self.storage.validated_step_data.get('method', {}))
        return PhoneDevice(key=self.get_key(), **kwargs)


class TwoFactorPhoneDeleteView(BaseMyAccountView, PhoneDeleteView):

    def get_success_url(self):
        messages.add_message(self.request, messages.SUCCESS, ugettext_lazy("Phone number removed."))
        return reverse(TwoFactorProfileView.urlname)

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(PhoneDeleteView, self).dispatch(request, *args, **kwargs)


class TwoFactorResetView(TwoFactorSetupView):
    urlname = 'reset'

    form_list = (
        ('welcome_reset', HQEmptyForm),
        ('method', HQTwoFactorMethodForm),
        ('generator', HQTOTPDeviceForm),
        ('sms', HQPhoneNumberForm),
        ('call', HQPhoneNumberForm),
        ('validation', HQDeviceValidationForm),
    )

    def get(self, request, *args, **kwargs):
        default_device(request.user).delete()
        return super(TwoFactorResetView, self).get(request, *args, **kwargs)


class BaseProjectDataView(BaseDomainView):
    section_name = ugettext_noop("Data")

    @property
    def section_url(self):
        return reverse('data_interfaces_default', args=[self.domain])


@require_POST
@login_required
def new_api_key(request):
    api_key = ApiKey.objects.get(user=request.user)
    api_key.key = api_key.generate_key()
    api_key.save()
    return HttpResponse(api_key.key)


@quickcache(['data'])
def get_qrcode(data):
    """
    Return a QR Code PNG (binary data)
    """
    image = qrcode.make(data)
    output = BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


class EnableMobilePrivilegesView(BaseMyAccountView):
    urlname = 'enable_mobile_privs'
    page_title = ugettext_lazy("Enable Privileges on Mobile")
    template_name = 'settings/enable_superuser.html'

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        message_v1 = json.dumps([
            {'username': request.user.username},
            {'flag': MULTIPLE_APPS_UNLIMITED.slug}
        ]).replace(' ', '').encode('utf-8')

        message_v2 = json.dumps([
            {'username': request.user.username},
            {'flags': [MULTIPLE_APPS_UNLIMITED.slug, ADVANCED_SETTINGS_ACCESS.slug]}
        ]).replace(' ', '').encode('utf-8')

        qrcode_data = json.dumps({
            'username': request.user.username,
            'version': 2,
            'flag': MULTIPLE_APPS_UNLIMITED.slug,
            'flags': [MULTIPLE_APPS_UNLIMITED.slug, ADVANCED_SETTINGS_ACCESS.slug],
            'signature': b64encode(sign(message_v1)).decode('utf-8'),
            'multiple_flags_signature': b64encode(sign(message_v2)).decode('utf-8')
        })

        qrcode = get_qrcode(qrcode_data)

        context = self.get_context_data(**kwargs)
        context['qrcode_64'] = b64encode(qrcode)
        return self.render_to_response(context)
