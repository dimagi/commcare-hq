import json
import re
from base64 import b64encode
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy, ugettext_noop
from django.views.decorators.debug import sensitive_post_parameters

import qrcode
from memoized import memoized
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

from corehq.apps.domain.extension_points import has_custom_clean_password
from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso.utils.request_helpers import is_request_using_sso
from dimagi.utils.web import json_response

import langcodes
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    login_required,
    require_superuser,
    two_factor_exempt,
)
from corehq import toggles
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.utils import sign, update_session_language
from corehq.apps.hqwebapp.views import BaseSectionPageView, CRUDPaginatedViewMixin
from corehq.apps.settings.exceptions import DuplicateApiKeyName
from corehq.apps.settings.forms import (
    HQApiKeyForm,
    HQDeviceValidationForm,
    HQEmptyForm,
    HQPasswordChangeForm,
    HQPhoneNumberForm,
    HQPhoneNumberMethodForm,
    HQTOTPDeviceForm,
    HQTwoFactorMethodForm,
)
from corehq.apps.users.models import HQApiKey
from corehq.apps.users.forms import AddPhoneNumberForm
from corehq.apps.users.util import log_user_change
from corehq.const import USER_CHANGE_VIA_WEB
from corehq.mobile_flags import (
    ADVANCED_SETTINGS_ACCESS,
    MULTIPLE_APPS_UNLIMITED,
)
from corehq.util.quickcache import quickcache


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
    template_name = 'settings/edit_my_account.html'

    @two_factor_exempt
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(MyAccountSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def settings_form(self):
        language_choices = langcodes.get_all_langs_for_select()
        from corehq.apps.users.forms import UpdateMyAccountInfoForm
        try:
            domain = self.request.domain
        except AttributeError:
            domain = ''
        if self.request.method == 'POST':
            form = UpdateMyAccountInfoForm(
                self.request.POST,
                domain=domain,
                existing_user=self.request.couch_user,
                request=self.request,
            )
        else:
            form = UpdateMyAccountInfoForm(
                domain=domain,
                existing_user=self.request.couch_user,
                request=self.request,
            )
        form.load_language(language_choices)
        return form

    @property
    def page_context(self):
        user = self.request.couch_user
        return {
            'form': self.settings_form,
            'add_phone_number_form': AddPhoneNumberForm(),
            'phonenumbers': user.phone_numbers_extended(user),
            'user_type': 'mobile' if user.is_commcare_user() else 'web',
        }

    def phone_number_is_valid(self):
        return (
            isinstance(self.phone_number, str)
            and re.compile(r'^\d+$').match(self.phone_number) is not None
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
    def page_context(self):
        return {
            'domains': [{
                'name': d,
                'is_admin': self.request.couch_user.is_domain_admin(d)
            } for d in self.request.couch_user.get_domains()],
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
                log_user_change(None, couch_user=request.couch_user,
                                changed_by_user=request.couch_user, changed_via=USER_CHANGE_VIA_WEB,
                                message=_("Removed from domain '{domain_name}'").format(
                                    domain_name=self.domain_to_remove),
                                domain_required_for_log=False,
                                )
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
        is_using_sso = (
            toggles.ENTERPRISE_SSO.enabled_for_request(self.request)
            and is_request_using_sso(self.request)
        )
        idp_name = None
        if is_using_sso:
            idp = IdentityProvider.get_active_identity_provider_by_username(
                self.request.user.username
            )
            idp_name = idp.name
        return {
            'form': self.password_change_form,
            'hide_password_feedback': has_custom_clean_password(),
            'is_using_sso': is_using_sso,
            'idp_name': idp_name,
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

    @property
    def page_context(self):
        if not (toggles.ENTERPRISE_SSO.enabled_for_request(self.request)
                and is_request_using_sso(self.request)):
            return {}

        idp = IdentityProvider.get_active_identity_provider_by_username(
            self.request.user.username
        )
        return {
            'is_using_sso': True,
            'idp_name': idp.name,
        }


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

    @property
    def page_context(self):
        return {
            "link_to_webapps": _show_link_to_webapps(self.request.couch_user),
        }


class TwoFactorBackupTokensView(BaseMyAccountView, BackupTokensView):
    urlname = 'two_factor_backup_tokens'
    template_name = 'two_factor/core/backup_tokens.html'
    page_title = ugettext_lazy("Two Factor Authentication Backup Tokens")

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(TwoFactorBackupTokensView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            "link_to_webapps": _show_link_to_webapps(self.request.couch_user),
        }


def _show_link_to_webapps(user):
    if user and user.is_commcare_user():
        if user.domain_memberships:
            membership = user.domain_memberships[0]
            if membership.role and membership.role.default_landing_page == "webapps":
                if toggles.TWO_STAGE_USER_PROVISIONING.enabled(membership.domain):
                    return True
    return False


class TwoFactorDisableView(BaseMyAccountView, DisableView):
    urlname = 'two_factor_disable'
    template_name = 'two_factor/profile/disable.html'
    page_title = ugettext_lazy("Remove Two-Factor Authentication")

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
        context['qrcode_64'] = b64encode(qrcode).decode('utf8')
        return self.render_to_response(context)


class ApiKeyView(BaseMyAccountView, CRUDPaginatedViewMixin):
    page_title = ugettext_lazy("API Keys")
    urlname = "user_api_keys"

    template_name = "settings/user_api_keys.html"

    @property
    def base_query(self):
        return HQApiKey.objects.filter(user=self.request.user)

    @property
    def total(self):
        return self.base_query.count()

    @property
    def column_names(self):
        return [
            _("Name"),
            _("API Key"),
            _("Project"),
            _("IP Allowlist"),
            _("Created"),
            _("Delete"),
        ]

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def paginated_list(self):
        for api_key in self.base_query.order_by('-created').all():
            redacted_key = f"{api_key.key[0:4]}…{api_key.key[-4:]}"
            yield {
                "itemData": {
                    "id": api_key.id,
                    "name": api_key.name,
                    "key": redacted_key,
                    "domain": api_key.domain or _('All Projects'),
                    "ip_allowlist": (
                        ", ".join(api_key.ip_allowlist)
                        if api_key.ip_allowlist else _("All IP Addresses")
                    ),
                    "created": api_key.created.strftime('%Y-%m-%d %H:%M:%S'),
                },
                "template": "base-user-api-key-template",
            }

    def post(self, *args, **kwargs):
        return self.paginate_crud_response

    create_item_form_class = "form form-horizontal"

    def get_create_form(self, is_blank=False):
        if self.request.method == 'POST' and not is_blank:
            return HQApiKeyForm(self.request.POST, couch_user=self.request.couch_user)
        return HQApiKeyForm(couch_user=self.request.couch_user)

    def get_create_item_data(self, create_form):
        try:
            new_api_key = create_form.create_key(self.request.user)
        except DuplicateApiKeyName:
            return {'error': _(f"Api Key with name \"{create_form.cleaned_data['name']}\" already exists.")}
        copy_key_message = _("Copy this in a secure place. It will not be shown again.")
        return {
            'itemData': {
                'id': new_api_key.id,
                'name': new_api_key.name,
                'key': f"{new_api_key.key} ({copy_key_message})",
                "domain": new_api_key.domain or _('All Projects'),
                'ip_allowlist': new_api_key.ip_allowlist,
                'created': new_api_key.created.isoformat()
            },
            'template': 'new-user-api-key-template',
        }

    def get_deleted_item_data(self, item_id):
        deleted_key = HQApiKey.objects.get(id=item_id)
        deleted_key.delete()
        return {
            'itemData': {
                'name': deleted_key.name,
            },
            'template': 'deleted-user-api-key-template',
        }
