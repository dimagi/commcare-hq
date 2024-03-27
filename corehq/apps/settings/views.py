import json
import re
from base64 import b64encode
from io import BytesIO
from datetime import datetime

import pytz
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop
from django.views.decorators.debug import sensitive_post_parameters

import langcodes
import qrcode
from django_otp import devices_for_user
from memoized import memoized
from two_factor.plugins.phonenumber.utils import backup_phones
from two_factor.views import (
    BackupTokensView,
    DisableView,
    ProfileView,
    SetupCompleteView,
    SetupView,
)
from two_factor.plugins.phonenumber.views import (
    PhoneDeleteView,
    PhoneSetupView
)

from dimagi.utils.web import json_response

from corehq import toggles
from corehq.apps.domain.decorators import (
    active_domains_required,
    login_and_domain_required,
    login_required,
    require_superuser,
    two_factor_exempt,
)
from corehq.apps.domain.extension_points import has_custom_clean_password
from corehq.apps.domain.forms import clean_password
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.decorators import use_jquery_ui
from corehq.apps.hqwebapp.utils import sign
from corehq.apps.hqwebapp.utils.two_factor import user_can_use_phone
from corehq.apps.hqwebapp.views import (
    BaseSectionPageView,
    CRUDPaginatedViewMixin,
    not_found,
)
from corehq.apps.settings.exceptions import DuplicateApiKeyName
from corehq.apps.settings.forms import (
    HQApiKeyForm,
    HQDeviceValidationForm,
    HQEmptyForm,
    HQPasswordChangeForm,
    HQPhoneNumberMethodForm,
    HQTwoFactorMethodForm,
)
from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso.utils.request_helpers import is_request_using_sso
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.forms import AddPhoneNumberForm
from corehq.apps.users.models import HQApiKey
from corehq.apps.users.util import log_user_change
from corehq.const import USER_CHANGE_VIA_WEB, USER_DATETIME_FORMAT
from corehq.mobile_flags import (
    ADVANCED_SETTINGS_ACCESS,
    MULTIPLE_APPS_UNLIMITED,
)
from corehq.util.quickcache import quickcache
from corehq.util.timezones.conversions import ServerTime


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
    from corehq.apps.groups.models import Group
    from corehq.apps.users.models import CommCareUser

    users = CommCareUser.by_domain(domain)
    groups = Group.by_domain(domain)

    return json_response({
        'users': dict([(user.raw_username, user.user_id) for user in users]),
        'groups': dict([(group.name, group.get_id) for group in groups]),
    })


class BaseMyAccountView(BaseSectionPageView):
    section_name = gettext_lazy("My Account")

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
    page_title = gettext_lazy("My Information")
    template_name = 'settings/bootstrap3/edit_my_account.html'

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
            is_new_phone_number = self.phone_number not in user.phone_numbers
            user.add_phone_number(self.phone_number)
            user.save()
            if is_new_phone_number:
                log_user_change(
                    by_domain=None,
                    for_domain=None,
                    couch_user=user,
                    changed_by_user=user,
                    changed_via=USER_CHANGE_VIA_WEB,
                    change_messages=UserChangeMessage.phone_numbers_added([self.phone_number]),
                    by_domain_required_for_log=False,
                    for_domain_required_for_log=False,
                )
            messages.success(self.request, _("Phone number added."))
        else:
            messages.error(self.request, _("Invalid phone number format entered. "
                "Please enter number, including country code, in digits only."))
        return HttpResponseRedirect(reverse(MyAccountSettingsView.urlname))

    def process_delete_phone_number(self):
        self.request.couch_user.delete_phone_number(self.phone_number)
        log_user_change(
            by_domain=None,
            for_domain=None,
            couch_user=self.request.couch_user,
            changed_by_user=self.request.couch_user,
            changed_via=USER_CHANGE_VIA_WEB,
            change_messages=UserChangeMessage.phone_numbers_removed([self.phone_number]),
            by_domain_required_for_log=False,
            for_domain_required_for_log=False,
        )
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
            self.settings_form.update_user()

            res = redirect(reverse(MyAccountSettingsView.urlname))
            res.set_cookie(settings.LANGUAGE_COOKIE_NAME, self.request.couch_user.language)
            return res

        return self.get(request, *args, **kwargs)


class MyProjectsList(BaseMyAccountView):
    urlname = 'my_projects'
    page_title = gettext_lazy("My Projects")
    template_name = 'settings/bootstrap3/my_projects.html'

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
                'is_admin': self.request.couch_user.is_domain_admin(d),
                'session_timeout': Domain.secure_timeout(d) or "",
            } for d in self.request.couch_user.get_domains()],
            'web_user': self.request.couch_user.is_web_user,
            'show_session_timeout': self.request.user.is_superuser
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
                log_user_change(by_domain=None, for_domain=self.domain_to_remove, couch_user=request.couch_user,
                                changed_by_user=request.couch_user, changed_via=USER_CHANGE_VIA_WEB,
                                change_messages=UserChangeMessage.domain_removal(self.domain_to_remove),
                                by_domain_required_for_log=False,
                                )
                messages.success(request, _("You are no longer part of the project %s") % self.domain_to_remove)
            except Exception:
                messages.error(request, _("There was an error removing you from this project."))
        return self.get(request, *args, **kwargs)


class ChangeMyPasswordView(BaseMyAccountView):
    urlname = 'change_my_password'
    template_name = 'settings/change_my_password.html'
    page_title = gettext_lazy("Change My Password")

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
        is_using_sso = is_request_using_sso(self.request)
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
            try:
                clean_password(request.POST['new_password1'])
                self.password_change_form.save()
                messages.success(request, _("Your password was successfully changed!"))
            except ValidationError as e:
                messages.error(request, _(e.message))
        return self.get(request, *args, **kwargs)


class TwoFactorProfileView(BaseMyAccountView, ProfileView):
    urlname = 'two_factor_settings'
    template_name = 'two_factor/profile/profile.html'
    page_title = gettext_lazy("Two Factor Authentication")

    @method_decorator(active_domains_required)
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(TwoFactorProfileView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if is_request_using_sso(self.request):
            idp = IdentityProvider.get_active_identity_provider_by_username(
                self.request.user.username
            )
            context.update({
                'is_using_sso': True,
                'idp_name': idp.name,
            })
        elif context.get('default_device'):
            # Default device means the user has 2FA already enabled
            has_existing_backup_phones = bool(context.get('backup_phones'))
            context.update({
                'allow_phone_2fa': has_existing_backup_phones or user_can_use_phone(self.request.couch_user),
            })

        return context


class TwoFactorSetupView(BaseMyAccountView, SetupView):
    urlname = 'two_factor_setup'
    template_name = 'two_factor/core/setup.html'
    page_title = gettext_lazy("Two Factor Authentication Setup")

    form_list = (
        ('welcome', HQEmptyForm),
        ('method', HQTwoFactorMethodForm),
        # other forms are registered on startup in corehq.apps.hqwebapp.apps.HqWebAppConfig
    )

    @method_decorator(active_domains_required)
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add decorators
        return super(TwoFactorSetupView, self).dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        if step == 'method':
            kwargs['allow_phone_2fa'] = user_can_use_phone(self.request.couch_user)

        return kwargs

    def get_form_list(self):
        # It would be cool if we could specify our custom validation form in the form_list property
        # but SetupView.get_form_list hard codes the default validation form for 'sms' and 'call' methods.
        # https://github.com/jazzband/django-two-factor-auth/blob/1.15.5/two_factor/views/core.py#L510-L511
        form_list = super().get_form_list()
        if {'sms', 'call'} & set(form_list.keys()):
            form_list['validation'] = HQDeviceValidationForm
        return form_list


class TwoFactorSetupCompleteView(BaseMyAccountView, SetupCompleteView):
    urlname = 'two_factor_setup_complete'
    template_name = 'two_factor/core/setup_complete.html'
    page_title = gettext_lazy("Two Factor Authentication Setup Complete")

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
    page_title = gettext_lazy("Two Factor Authentication Backup Tokens")

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
    page_title = gettext_lazy("Remove Two-Factor Authentication")

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(TwoFactorDisableView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return DisableView.get(self, request, *args, **kwargs)


class TwoFactorPhoneSetupView(BaseMyAccountView, PhoneSetupView):
    urlname = 'two_factor_phone_setup'
    template_name = 'two_factor/core/phone_register.html'
    page_title = gettext_lazy("Two Factor Authentication Phone Setup")

    form_list = (
        ('setup', HQPhoneNumberMethodForm),
        ('validation', HQDeviceValidationForm),
    )

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        has_backup_phones = bool(backup_phones(self.request.user))
        if not (has_backup_phones or user_can_use_phone(request.couch_user)):
            # NOTE: this behavior could be seen as un-intuitive. If a domain is not authorized to use phone/sms,
            # we are still allowing full functionality if they have an existing backup phone. The primary reason
            # is so that a user can delete a backup number if needed. The ability to add in a new number is still
            # enabled just to prevent confusion -- it is expected to be an edge case.
            raise Http404

        return super(TwoFactorPhoneSetupView, self).dispatch(request, *args, **kwargs)

    def done(self, form_list, **kwargs):
        """
        Store the device and reload the page.
        """
        self.get_device(user=self.request.user, name='backup').save()
        messages.add_message(self.request, messages.SUCCESS, _("Phone number added."))
        return redirect(reverse(TwoFactorProfileView.urlname))


class TwoFactorPhoneDeleteView(BaseMyAccountView, PhoneDeleteView):

    def get_success_url(self):
        messages.add_message(self.request, messages.SUCCESS, gettext_lazy("Phone number removed."))
        return reverse(TwoFactorProfileView.urlname)

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # this is only here to add the login_required decorator
        return super(PhoneDeleteView, self).dispatch(request, *args, **kwargs)


class TwoFactorResetView(TwoFactorSetupView):
    urlname = 'reset'

    def get(self, request, *args, **kwargs):
        # avoid using django-two-factor-auth default_devices method because it adds a dynamic attribute
        # to the user object that we then have to cleanup before calling super
        # https://github.com/jazzband/django-two-factor-auth/blob/1.15.5/two_factor/utils.py#L9-L17
        for device in devices_for_user(request.user):
            if device.name == 'default':
                device.delete()
                break
        return super(TwoFactorResetView, self).get(request, *args, **kwargs)


class BaseProjectDataView(BaseDomainView):
    section_name = gettext_noop("Data")

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
    page_title = gettext_lazy("Enable Privileges on Mobile")
    template_name = 'settings/enable_superuser.html'

    def dispatch(self, request, *args, **kwargs):
        # raises a 404 if a user tries to access this page without the right authorizations
        if hasattr(request, 'couch_user') and self.is_user_authorized(request.couch_user):
            return super(BaseMyAccountView, self).dispatch(request, *args, **kwargs)
        return not_found(request)

    @staticmethod
    def is_user_authorized(couch_user):
        if (
            couch_user and couch_user.is_dimagi
            or toggles.MOBILE_PRIVILEGES_FLAG.enabled(couch_user.username)
        ):
            return True
        return False

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
    page_title = gettext_lazy("API Keys")
    urlname = "user_api_keys"

    template_name = "settings/bootstrap3/user_api_keys.html"

    @use_jquery_ui  # for datepicker
    def dispatch(self, request, *args, **kwargs):
        return super(ApiKeyView, self).dispatch(request, *args, **kwargs)

    @property
    def allowed_actions(self):
        return [
            'create',
            'delete',
            'paginate',
            'activate',
            'deactivate',
        ]

    @property
    def activate_response(self):
        return self._set_is_active_response(is_active=True)

    @property
    def deactivate_response(self):
        return self._set_is_active_response(is_active=False)

    def _set_is_active_response(self, is_active):
        key_id = self.parameters.get('id')
        api_key = self.base_query.get(pk=key_id)
        api_key.is_active = is_active
        api_key.deactivated_on = None if is_active else timezone.now()
        api_key.save()
        return {'success': True, 'itemData': self._to_json(api_key)}

    @property
    def base_query(self):
        return HQApiKey.all_objects.filter(user=self.request.user)

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
            _("Last Used"),
            _("Expiration Date"),
            _("Status"),
            _("Actions"),
        ]

    def _to_user_time(self, value):
        return (ServerTime(value)
                .user_time(pytz.timezone(self.request.couch_user.get_time_zone()))
                .done()
                .strftime(USER_DATETIME_FORMAT)) if value else '-'

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def paginated_list(self):
        for api_key in self.base_query.order_by('-created').all()[self.skip:self.skip + self.limit]:
            yield {
                "itemData": self._to_json(api_key),
                "template": "base-user-api-key-template",
            }

    def _to_json(self, api_key, redacted=True):
        if redacted:
            key = f"{api_key.key[0:4]}…{api_key.key[-4:]}"
        else:
            copy_msg = _("Copy this in a secure place. It will not be shown again.")
            key = f"{api_key.key} ({copy_msg})",

        if api_key.expiration_date and api_key.expiration_date < datetime.now():
            status = "expired"
        elif api_key.is_active:
            status = "active"
        else:
            status = "inactive"
        return {
            "id": api_key.id,
            "name": api_key.name,
            "key": key,
            "domain": api_key.domain or _('All Projects'),
            "ip_allowlist": (
                ", ".join(api_key.ip_allowlist)
                if api_key.ip_allowlist else _("All IP Addresses")
            ),
            "created": self._to_user_time(api_key.created),
            "last_used": self._to_user_time(api_key.last_used),
            "expiration_date": self._to_user_time(api_key.expiration_date),
            "status": status,
            "deactivated_on": self._to_user_time(api_key.deactivated_on),
            "is_active": api_key.is_active,
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
        return {
            'itemData': self._to_json(new_api_key, redacted=False),
            'template': 'new-user-api-key-template',
        }

    def get_deleted_item_data(self, item_id):
        deleted_key = self.base_query.get(id=item_id)
        deleted_key.delete()
        return {
            'itemData': {
                'name': deleted_key.name,
            },
            'template': 'deleted-user-api-key-template',
        }
