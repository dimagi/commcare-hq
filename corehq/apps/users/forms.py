import datetime
import json
import re
import secrets
import string

from django import forms
from django.conf import settings
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, validate_email
from django.forms.widgets import PasswordInput
from django.template.loader import get_template
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout, Submit
from django_countries.data import COUNTRIES
from memoized import memoized

from dimagi.utils.dates import get_date_from_month_and_year_string

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.analytics.tasks import set_analytics_opt_out
from corehq.apps.app_manager.models import validate_lang
from corehq.apps.custom_data_fields.edit_entity import CustomDataEditor
from corehq.apps.custom_data_fields.models import CustomDataFieldsProfile, PROFILE_SLUG
from corehq.apps.domain.extension_points import has_custom_clean_password
from corehq.apps.domain.forms import EditBillingAccountInfoForm, clean_password
from corehq.apps.domain.models import Domain
from corehq.apps.enterprise.models import (
    EnterpriseMobileWorkerSettings,
    EnterprisePermissions,
)
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import HQModalFormHelper
from corehq.apps.hqwebapp.utils.translation import format_html_lazy
from corehq.apps.hqwebapp.widgets import Select2Ajax, SelectToggle
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import user_can_access_location_id
from corehq.apps.programs.models import Program
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.reports.models import TableauUser
from corehq.apps.reports.util import (
    TableauGroupTuple,
    get_all_tableau_groups,
    get_allowed_tableau_groups_for_domain,
    get_tableau_groups_for_user,
    update_tableau_user,
)
from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso.utils.request_helpers import is_request_using_sso
from corehq.apps.user_importer.helpers import UserChangeLogger
from corehq.const import LOADTEST_HARD_LIMIT, USER_CHANGE_VIA_WEB
from corehq.pillows.utils import MOBILE_USER_TYPE, WEB_USER_TYPE
from corehq.toggles import (
    TWO_STAGE_USER_PROVISIONING,
    TWO_STAGE_USER_PROVISIONING_BY_SMS,
)

from ..hqwebapp.signals import clear_login_attempts
from .audit.change_messages import UserChangeMessage
from .dbaccessors import user_exists
from .models import CouchUser, DeactivateMobileWorkerTrigger, UserRole
from .util import cc_user_domain, format_username, log_user_change

UNALLOWED_MOBILE_WORKER_NAMES = ('admin', 'demo_user')
STRONG_PASSWORD_LEN = 12


def get_mobile_worker_max_username_length(domain):
    """
    The auth_user table only allows for usernames up to 128 characters long.
    The code used to allow for usernames up to 80 characters, but that
    didn't properly take into consideration the fact that the domain and
    site name vary.
    """
    return min(128 - len(cc_user_domain(domain)) - 1, 80)


def clean_mobile_worker_username(
    domain,
    username,
    name_too_long_message=None,
    name_reserved_message=None,
    name_exists_message=None,
):

    max_username_length = get_mobile_worker_max_username_length(domain)

    if len(username) > max_username_length:
        raise forms.ValidationError(
            name_too_long_message
            or _(
                'Username %(username)s is too long.  Must be under '
                '%(max_length)s characters.'
            ) % {'username': username, 'max_length': max_username_length}
        )

    if username in UNALLOWED_MOBILE_WORKER_NAMES:
        raise forms.ValidationError(
            name_reserved_message
            or _('The username "%(username)s" is reserved for CommCare.')
            % {'username': username}
        )

    username = format_username(username, domain)
    validate_username(username)

    exists = user_exists(username)
    if exists.exists:
        if exists.is_deleted:
            raise forms.ValidationError(_('This username was used previously.'))
        raise forms.ValidationError(
            name_exists_message or _('This Mobile Worker already exists.')
        )

    return username


def clean_deactivate_after_date(deactivate_after_date):
    if not deactivate_after_date:
        return None
    try:
        return get_date_from_month_and_year_string(deactivate_after_date)
    except ValueError:
        raise forms.ValidationError(
            _("Invalid Deactivation Date format (expects MM-YYYY).")
        )


def wrapped_language_validation(value):
    try:
        validate_lang(value)
    except ValueError:
        raise forms.ValidationError(_(
            "{code} is not a valid language code. Please enter a valid "
            "ISO-639 two- or three-digit code."
        ).format({'code': value}))


def generate_strong_password():
    # https://docs.python.org/3/library/secrets.html#recipes-and-best-practices
    possible = string.punctuation + string.ascii_letters + string.digits
    while True:
        password = ''.join(secrets.choice(possible)
                           for __ in range(STRONG_PASSWORD_LEN))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in string.punctuation for c in password)
        ):
            break
    return password


class LanguageField(forms.CharField):
    """
    Adds language code validation to a field
    """

    def __init__(self, *args, **kwargs):
        super(LanguageField, self).__init__(*args, **kwargs)
        self.min_length = 2
        self.max_length = 3

    default_error_messages = {
        'invalid': gettext_lazy('Please enter a valid two or three digit language code.'),
    }
    default_validators = [wrapped_language_validation]


class BaseUpdateUserForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain')
        self.existing_user = kwargs.pop('existing_user')
        self.request = kwargs.pop('request')
        super(BaseUpdateUserForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        for prop in self.direct_properties:
            self.initial[prop] = getattr(self.existing_user, prop, "")

    @property
    def direct_properties(self):
        return []

    def clean_email(self):
        return self.cleaned_data['email'].lower()

    def update_user(self, save=True):
        is_update_successful = False
        props_updated = {}

        for prop in self.direct_properties:
            if getattr(self.existing_user, prop) != self.cleaned_data[prop]:
                props_updated[prop] = self.cleaned_data[prop]
            setattr(self.existing_user, prop, self.cleaned_data[prop])
            is_update_successful = True

        if is_update_successful and save:
            self.existing_user.save()
            if props_updated:
                # This form is used either by a web user to edit their info where there is no domain or
                # to edit a web/commcare user on a domain, so by_ and for_domain would be the same domain
                log_user_change(
                    by_domain=self.request.domain if self.domain else None,
                    for_domain=self.request.domain if self.domain else None,
                    couch_user=self.existing_user,
                    changed_by_user=self.request.couch_user,
                    changed_via=USER_CHANGE_VIA_WEB,
                    fields_changed=props_updated,
                    by_domain_required_for_log=bool(self.domain),
                    for_domain_required_for_log=bool(self.domain)
                )
        return is_update_successful, props_updated


class UpdateUserRoleForm(BaseUpdateUserForm):
    role = forms.ChoiceField(choices=(), required=False)

    def clean_role(self):
        role = self.cleaned_data.get('role')
        if role == 'none' and self.existing_user.is_web_user():
            raise forms.ValidationError(_('Role is required for web users.'))
        return role

    def update_user(self, metadata_updated=False, profile_updated=False):
        is_update_successful, props_updated = super(UpdateUserRoleForm, self).update_user(save=False)
        role_updated = False
        user_new_role = None

        if self.domain and 'role' in self.cleaned_data:
            role = self.cleaned_data['role']
            user_current_role = self.existing_user.get_role(domain=self.domain)
            try:
                self.existing_user.set_role(self.domain, role)
                if self.existing_user.is_commcare_user():
                    self.existing_user.save(spawn_task=True)
                else:
                    self.existing_user.save()
                is_update_successful = True
            except KeyError:
                pass
            else:
                user_new_role = self.existing_user.get_role(self.domain, checking_global_admin=False)
                role_updated = self._role_updated(user_current_role, user_new_role)
        elif is_update_successful:
            self.existing_user.save()

        if is_update_successful and (props_updated or role_updated or metadata_updated):
            change_messages = {}
            user_data = self.existing_user.get_user_data(self.domain)
            profile_id = user_data.profile_id
            if role_updated:
                change_messages.update(UserChangeMessage.role_change(user_new_role))
            if metadata_updated:
                props_updated['user_data'] = user_data.raw
            if profile_updated:
                profile_name = None
                if profile_id:
                    profile_name = CustomDataFieldsProfile.objects.get(id=profile_id).name
                change_messages.update(UserChangeMessage.profile_info(profile_id, profile_name))
            # this form is used to edit a web/commcare user on a domain so set domain for both by_ and for_domain
            log_user_change(
                by_domain=self.request.domain,
                for_domain=self.domain,
                couch_user=self.existing_user,
                changed_by_user=self.request.couch_user,
                changed_via=USER_CHANGE_VIA_WEB,
                fields_changed=props_updated,
                change_messages=change_messages
            )
        return is_update_successful

    @staticmethod
    def _role_updated(old_role, new_role):
        if bool(old_role) ^ bool(new_role):
            return True
        if old_role and new_role and new_role.get_qualified_id() != old_role.get_qualified_id():
            return True
        return False

    def load_roles(self, role_choices=None, current_role=None):
        if role_choices is None:
            role_choices = []
        self.fields['role'].choices = role_choices

        if current_role:
            self.initial['role'] = current_role


class BaseUserInfoForm(forms.Form):
    first_name = forms.CharField(label=gettext_lazy('First Name'), max_length=30, required=False)
    last_name = forms.CharField(label=gettext_lazy('Last Name'), max_length=30, required=False)
    email = forms.EmailField(label=gettext_lazy("E-Mail"), max_length=75, required=False)
    language = forms.ChoiceField(
        choices=(),
        initial=None,
        required=False,
        help_text=gettext_lazy(
            "<i class=\"fa fa-info-circle\"></i> "
            "Becomes default language seen in Web Apps and reports (if applicable), "
            "but does not affect mobile applications. "
            "Supported languages for reports are en, fra (partial), and hin (partial)."
        )
    )

    def load_language(self, language_choices=None):
        if language_choices is None:
            language_choices = []
        self.fields['language'].choices = [('', '')] + language_choices


class UpdateMyAccountInfoForm(BaseUpdateUserForm, BaseUserInfoForm):
    analytics_enabled = forms.BooleanField(
        required=False,
        label=gettext_lazy("Enable Tracking"),
        help_text=gettext_lazy(
            "Allow Dimagi to collect usage information to improve CommCare. "
            "You can learn more about the information we collect and the ways "
            "we use it in our "
            '<a href="http://www.dimagi.com/terms/latest/privacy/">privacy policy</a>'
        ),
    )

    def __init__(self, *args, **kwargs):
        from corehq.apps.settings.views import ApiKeyView
        self.user = kwargs['existing_user']
        self.is_using_sso = is_request_using_sso(kwargs['request'])
        super(UpdateMyAccountInfoForm, self).__init__(*args, **kwargs)
        self.username = self.user.username

        username_controls = []
        if self.username:
            username_controls.append(hqcrispy.StaticField(
                gettext_lazy('Username'), self.username)
            )

        self.fields['language'].label = gettext_lazy("My Language")

        self.new_helper = FormHelper()
        self.new_helper.form_method = 'POST'
        self.new_helper.form_class = 'form-horizontal'
        self.new_helper.attrs = {
            'name': 'user_information',
        }
        self.new_helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.new_helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        basic_fields = [
            crispy.Div(*username_controls),
            'first_name',
            'last_name',
        ]

        if self.is_using_sso:
            idp = IdentityProvider.get_active_identity_provider_by_username(
                self.request.user.username
            )
            self.fields['email'].initial = self.user.email
            self.fields['email'].help_text = _(
                "This email is managed by {} and cannot be edited."
            ).format(idp.name)

            # It is the presence of the "readonly" attribute that determines
            # whether an input is readonly. Its value does not matter.
            basic_fields.append(crispy.Field('email', readonly="readonly"))
        else:
            basic_fields.append('email')

        if self.set_analytics_enabled:
            basic_fields.append(twbscrispy.PrependedText('analytics_enabled', ''),)

        self.new_helper.layout = crispy.Layout(
            crispy.Fieldset(
                gettext_lazy("Basic"),
                *basic_fields
            ),
            (hqcrispy.FieldsetAccordionGroup if self.collapse_other_options else crispy.Fieldset)(
                gettext_lazy("Other Options"),
                'language',
                crispy.Div(hqcrispy.StaticField(
                    gettext_lazy('API Key'),
                    format_html_lazy(
                        gettext_lazy('API key management has moved <a href="{}">here</a>.'),
                        reverse(ApiKeyView.urlname)),
                )),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    gettext_lazy("Update My Information"),
                    type='submit',
                    css_class='btn-primary',
                )
            )
        )

    @property
    def set_analytics_enabled(self):
        return not settings.ENTERPRISE_MODE

    @property
    def collapse_other_options(self):
        return self.user.is_commcare_user()

    @property
    def direct_properties(self):
        result = list(self.fields)
        if self.is_using_sso:
            result.remove('email')
        if not self.set_analytics_enabled:
            result.remove('analytics_enabled')
        return result

    def update_user(self, save=True, **kwargs):
        if save and self.set_analytics_enabled:
            analytics_enabled = self.cleaned_data['analytics_enabled']
            if self.user.analytics_enabled != analytics_enabled:
                set_analytics_opt_out(self.user, analytics_enabled)
        return super(UpdateMyAccountInfoForm, self).update_user(save=save, **kwargs)


class UpdateCommCareUserInfoForm(BaseUserInfoForm, UpdateUserRoleForm):

    # The value for this field is managed by CommCareUserActionForm. Defining
    # the field here allows us to use CommCareUserFormSet.update_user() to set
    # this property on the user.
    loadtest_factor = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
    )

    deactivate_after_date = forms.CharField(
        label=gettext_lazy("Deactivate After"),
        required=False,
        help_text=gettext_lazy(
            "When specified, the mobile worker is automatically deactivated "
            "on the first day of the month and year selected."
        )
    )

    def __init__(self, *args, **kwargs):
        super(UpdateCommCareUserInfoForm, self).__init__(*args, **kwargs)
        self.show_deactivate_after_date = EnterpriseMobileWorkerSettings.is_domain_using_custom_deactivation(
            self.domain
        )

        if self.show_deactivate_after_date:
            initial_deactivate_after_date = DeactivateMobileWorkerTrigger.get_deactivate_after_date(
                self.domain, self.existing_user.user_id
            )
            if initial_deactivate_after_date is not None:
                self.initial['deactivate_after_date'] = initial_deactivate_after_date.strftime('%m-%Y')
        else:
            del self.fields['deactivate_after_date']

    def clean_deactivate_after_date(self):
        return clean_deactivate_after_date(self.cleaned_data['deactivate_after_date'])

    @property
    def direct_properties(self):
        indirect_props = ['role', 'deactivate_after_date']
        return [k for k in self.fields if k not in indirect_props]

    def update_user(self, **kwargs):
        if self.show_deactivate_after_date:
            DeactivateMobileWorkerTrigger.update_trigger(
                self.domain,
                self.existing_user.user_id,
                self.cleaned_data['deactivate_after_date']
            )
        return super().update_user(**kwargs)


class CommCareUserActionForm(BaseUpdateUserForm):

    loadtest_factor = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=LOADTEST_HARD_LIMIT,
        help_text=gettext_lazy(
            "Multiply this user's case load by this number for load testing "
            "on phones."
        ),
        widget=forms.TextInput()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.initial['loadtest_factor'] = self.existing_user.loadtest_factor or 1

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Load testing"),
                crispy.Field(
                    'loadtest_factor',
                    # This field is being added to the "user_information" form.
                    # This allows us to reuse CommCareUserFormSet.update_user()
                    # to set this property on the user. The "user_information"
                    # form is defined in
                    # corehq/apps/users/templates/users/partials/basic_info_form.html
                    form='user_information',
                ),
                hqcrispy.FormActions(
                    crispy.ButtonHolder(
                        StrictButton(
                            _('Update user'),
                            type='submit',
                            css_class='btn-primary',
                            # This button submits the "user_information" form.
                            form='user_information',
                        )
                    )
                )
            )
        )


class RoleForm(forms.Form):

    def __init__(self, *args, **kwargs):
        if 'role_choices' in kwargs:
            role_choices = kwargs.pop('role_choices')
        else:
            role_choices = ()
        super(RoleForm, self).__init__(*args, **kwargs)
        self.fields['role'].choices = role_choices


class SetUserPasswordForm(SetPasswordForm):

    new_password1 = forms.CharField(
        label=gettext_noop("New password"),
        widget=forms.PasswordInput(),
    )

    def __init__(self, project, user_id, **kwargs):
        super(SetUserPasswordForm, self).__init__(**kwargs)
        self.project = project
        initial_password = ''

        if self.project.strong_mobile_passwords:
            self.fields['new_password1'].widget = forms.TextInput()
            self.fields['new_password1'].help_text = format_html_lazy(
                '<span id="help_text" data-bind="html: passwordHelp, css: color, click: firstSuggestion">')
            initial_password = generate_strong_password()

        self.helper = FormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_tag = False

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_action = reverse("change_password", args=[project.name, user_id])
        if self.project.strong_mobile_passwords:
            submitButton = hqcrispy.FormActions(
                crispy.ButtonHolder(
                    Submit('submit', _('Reset Password'),
                           data_bind="enable: passwordSufficient(), click: submitCheck")
                )
            )
        else:
            submitButton = hqcrispy.FormActions(
                crispy.ButtonHolder(
                    Submit('submit', _('Reset Password'))
                )
            )
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Reset Password for Mobile Worker"),
                crispy.Field(
                    'new_password1',
                    data_bind="initializeValue: password, value: password, valueUpdate: 'input'",
                    value=initial_password,
                ),
                crispy.Field(
                    'new_password2',
                    value=initial_password,
                ),
                submitButton,
                css_class="check-password",
            ),
        )

    def clean_new_password1(self):
        password1 = self.cleaned_data.get('new_password1')
        if self.project.strong_mobile_passwords:
            return clean_password(password1)
        return password1

    def save(self, commit=True):
        user = super().save(commit=commit)
        couch_user = CouchUser.from_django_user(self.user)
        clear_login_attempts(couch_user)
        return user


class CommCareAccountForm(forms.Form):
    """
    Form for CommCareAccounts
    """
    username = forms.CharField(required=True)
    password_1 = forms.CharField(label=gettext_lazy('Password'), widget=PasswordInput(),
                                 required=True, min_length=1)
    password_2 = forms.CharField(label=gettext_lazy('Password (reenter)'), widget=PasswordInput(),
                                 required=True, min_length=1)
    phone_number = forms.CharField(
        max_length=80,
        required=False,
        help_text=gettext_lazy("Please enter number, including "
                               "international code, in digits only.")
    )

    def __init__(self, *args, **kwargs):
        if 'domain' not in kwargs:
            raise Exception('Expected kwargs: domain')
        self.domain = kwargs.pop('domain', None)
        super(forms.Form, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-lg-3'
        self.helper.field_class = 'col-lg-9'
        self.helper.layout = Layout(
            Fieldset(
                _("Mobile Worker's Primary Information"),
                'username',
                'password_1',
                'password_2',
                'phone_number',
            )
        )

    def clean_username(self):
        return clean_mobile_worker_username(
            self.domain,
            self.cleaned_data.get('username')
        )

    def clean_phone_number(self):
        phone_number = self.cleaned_data['phone_number']
        phone_number = re.sub(r'\s|\+|\-', '', phone_number)
        if phone_number == '':
            return None
        elif not re.match(r'\d+$', phone_number):
            raise forms.ValidationError(_("%s is an invalid phone number." % phone_number))
        return phone_number

    def clean(self):
        try:
            password_1 = self.cleaned_data['password_1']
            password_2 = self.cleaned_data['password_2']
        except KeyError:
            pass
        else:
            if password_1 != password_2:
                raise forms.ValidationError("Passwords do not match")

        return self.cleaned_data


validate_username = EmailValidator(message=gettext_lazy('Username contains invalid characters.'))


class NewMobileWorkerForm(forms.Form):
    username = forms.CharField(
        max_length=50,
        required=True,
        help_text="""
            <span data-bind="visible: $root.usernameAvailabilityStatus() !== $root.STATUS.NONE">
                <i class="fa fa-circle-notch fa-spin"
                   data-bind="visible: $root.usernameAvailabilityStatus() === $root.STATUS.PENDING"></i>
                <i class="fa fa-check"
                   data-bind="visible: $root.usernameAvailabilityStatus() === $root.STATUS.SUCCESS"></i>
                <i class="fa-solid fa-triangle-exclamation"
                   data-bind="visible: $root.usernameAvailabilityStatus() === $root.STATUS.WARNING ||
                                       $root.usernameAvailabilityStatus() === $root.STATUS.ERROR"></i>
                <!-- ko text: $root.usernameStatusMessage --><!-- /ko -->
            </span>
        """,
        label=gettext_noop("Username"),
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        label=gettext_noop("First Name"),
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        label=gettext_noop("Last Name")
    )
    location_id = forms.CharField(
        label=gettext_noop("Location"),
        required=False,
    )
    force_account_confirmation = forms.BooleanField(
        label=gettext_noop("Require Account Confirmation?"),
        help_text=gettext_noop(
            "The user's account will not be active until "
            "they have confirmed their email and set a password."
        ),
        required=False,
    )
    email = forms.EmailField(
        label=gettext_noop("Email"),
        required=False,
        help_text="""
            <span data-bind="visible: $root.emailStatus() !== $root.STATUS.NONE">
                <i class="fa-solid fa-triangle-exclamation"
                   data-bind="visible: $root.emailStatus() === $root.STATUS.ERROR"></i>
                <!-- ko text: $root.emailStatusMessage --><!-- /ko -->
            </span>
        """
    )
    send_account_confirmation_email = forms.BooleanField(
        label=gettext_noop("Send Account Confirmation Email Now?"),
        help_text=gettext_noop(
            "The user will be sent their account confirmation email now. "
            "Otherwise it must be sent manually from the Mobile Worker 'Deactivated Users' list."
        ),
        required=False,
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(),
        required=True,
        min_length=1,
        label=gettext_noop("Password"),
    )
    deactivate_after_date = forms.CharField(
        label=gettext_lazy("Deactivate After"),
        required=False,
        help_text=gettext_lazy(
            "When specified, the mobile worker is automatically deactivated "
            "on the first day of the month and year selected."
        ),
    )
    force_account_confirmation_by_sms = forms.BooleanField(
        label=gettext_noop("Require Account Confirmation by SMS?"),
        help_text=gettext_noop(
            "If checked, the user will be sent a confirmation SMS and asked to set their password."
        ),
        required=False,
    )
    phone_number = forms.CharField(
        required=False,
        label=gettext_noop("Phone Number"),
        help_text=gettext_noop(
            """
            <div data-bind="visible: $root.phoneStatusMessage().length === 0">
                    Please enter number including country code, without (+) and in digits only.
            </div>
            <div id="phone-error">
                <span data-bind="visible: $root.phoneStatus() !== $root.STATUS.NONE">
                    <i class="fa-solid fa-triangle-exclamation"
                    data-bind="visible: $root.phoneStatus() === $root.STATUS.ERROR"></i>
                    <!-- ko text: $root.phoneStatusMessage --><!-- /ko -->
                </span>
            </div>
        """)
    )

    def __init__(self, project, request_user, *args, **kwargs):
        super(NewMobileWorkerForm, self).__init__(*args, **kwargs)
        email_string = "@{}.{}".format(project.name, settings.HQ_ACCOUNT_ROOT)
        max_chars_username = 80 - len(email_string)
        self.project = project
        self.domain = self.project.name
        self.request_user = request_user
        self.can_access_all_locations = request_user.has_permission(self.domain, 'access_all_locations')

        self.show_deactivate_after_date = EnterpriseMobileWorkerSettings.is_domain_using_custom_deactivation(
            self.domain
        )

        if not self.show_deactivate_after_date:
            del self.fields['deactivate_after_date']

        if not self.can_access_all_locations:
            self.fields['location_id'].required = True

        if self.project.strong_mobile_passwords:
            # Use normal text input so auto-generated strong password is visible
            self.fields['new_password'].widget = forms.TextInput()
            self.fields['new_password'].help_text = format_html_lazy(
                '<i class="fa fa-warning"></i>{}<br />',
                gettext_lazy(
                    'This password is automatically generated. '
                    'Please copy it or create your own. It will not be shown again.'))

        if project.uses_locations:
            self.fields['location_id'].widget = forms.Select()
            location_field = crispy.Field(
                'location_id',
                data_bind='value: location_id',
                data_query_url=reverse('location_search', args=[self.domain]),
            )
        else:
            location_field = crispy.Hidden(
                'location_id',
                '',
                data_bind='value: location_id',
            )

        self.two_stage_provisioning_enabled = TWO_STAGE_USER_PROVISIONING.enabled(self.domain)
        if self.two_stage_provisioning_enabled:
            confirm_account_field = crispy.Field(
                'force_account_confirmation',
                data_bind='checked: force_account_confirmation',
            )
            email_field = crispy.Div(
                crispy.Field(
                    'email',
                    data_bind="value: email, valueUpdate: 'keyup'",
                ),
                data_bind='''
                    css: {
                        'has-error': $root.emailStatus() === $root.STATUS.ERROR,
                    },
                '''
            )
            send_email_field = crispy.Field(
                'send_account_confirmation_email',
                data_bind='checked: send_account_confirmation_email, enable: sendConfirmationEmailEnabled',
            )
        else:
            confirm_account_field = crispy.Hidden(
                'force_account_confirmation',
                '',
                data_bind='value: force_account_confirmation',
            )
            email_field = crispy.Hidden(
                'email',
                '',
                data_bind='value: email',
            )
            send_email_field = crispy.Hidden(
                'send_account_confirmation_email',
                '',
                data_bind='value: send_account_confirmation_email',
            )

        if TWO_STAGE_USER_PROVISIONING_BY_SMS.enabled(self.domain):
            confirm_account_by_sms_field = crispy.Field(
                'force_account_confirmation_by_sms',
                data_bind='checked: force_account_confirmation_by_sms',
            )
            phone_number_field = crispy.Div(
                crispy.Field(
                    'phone_number',
                    data_bind="value: phone_number, valueUpdate: 'keyup'",
                ),
                data_bind='''
                    css: {
                        'has-error': $root.phoneStatus() === $root.STATUS.ERROR,
                    },
                '''
            )
        else:
            confirm_account_by_sms_field = crispy.Hidden(
                'force_account_confirmation_by_sms',
                '',
                data_bind='value: force_account_confirmation_by_sms',
            )
            phone_number_field = crispy.Hidden(
                'phone_number',
                '',
                data_bind='value: phone_number',
            )

        self.helper = HQModalFormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                _('Basic Information'),
                crispy.Div(
                    crispy.Field(
                        'username',
                        data_bind="value: username, valueUpdate: 'keyup'",
                        maxlength=max_chars_username,
                    ),
                    data_bind='''
                        css: {
                            'has-pending': $root.usernameAvailabilityStatus() === $root.STATUS.PENDING,
                            'has-success': $root.usernameAvailabilityStatus() === $root.STATUS.SUCCESS,
                            'has-warning': $root.usernameAvailabilityStatus() === $root.STATUS.WARNING,
                            'has-error': $root.usernameAvailabilityStatus() === $root.STATUS.ERROR,
                        },
                    '''
                ),
                crispy.Field(
                    'first_name',
                    data_bind='value: first_name',
                ),
                crispy.Field(
                    'last_name',
                    data_bind='value: last_name',
                ),
                location_field,
                confirm_account_field,
                email_field,
                send_email_field,
                confirm_account_by_sms_field,
                phone_number_field,
                crispy.Div(
                    hqcrispy.B3MultiField(
                        _("Password"),
                        InlineField(
                            'new_password',
                            data_bind="value: password, valueUpdate: 'input', enable: passwordEnabled",
                        ),
                        crispy.HTML('''
                            <p class="help-block" data-bind="if: $root.isSuggestedPassword">
                                <i class="fa fa-warning"></i> {suggested}
                            </p>
                            <p class="help-block" data-bind="ifnot: $root.isSuggestedPassword()">
                                <!-- ko ifnot: $root.skipStandardValidations() -->
                                    <!-- ko if: $root.passwordStatus() === $root.STATUS.SUCCESS -->
                                        <i class="fa fa-check"></i> {strong}
                                    <!-- /ko -->
                                    <!-- ko if: $root.passwordStatus() === $root.STATUS.WARNING -->
                                        {almost}
                                    <!-- /ko -->
                                    <!-- ko if: $root.passwordStatus() === $root.STATUS.ERROR -->
                                        <!-- ko ifnot: $root.passwordSatisfyLength() -->
                                            <i class="fa fa-warning"></i> {short}
                                        <!-- /ko -->
                                        <!-- ko if: $root.passwordSatisfyLength() -->
                                            <i class="fa fa-warning"></i> {weak}
                                        <!-- /ko -->
                                    <!-- /ko -->
                                <!-- /ko -->

                                <!-- ko if: $root.skipStandardValidations() -->
                                    <i class="fa fa-info-circle"></i> {custom_warning}
                                <!-- /ko -->
                                <!-- ko if: $root.passwordStatus() === $root.STATUS.DISABLED -->
                                    <!-- ko if: $root.stagedUser().force_account_confirmation() -->
                                        <i class="fa fa-warning"></i> {disabled_email}
                                    <!-- /ko -->
                                    <!-- ko if: !($root.stagedUser().force_account_confirmation())
                                    && $root.stagedUser().force_account_confirmation_by_sms() -->
                                        <i class="fa fa-warning"></i> {disabled_phone}
                                    <!-- /ko -->
                                <!-- /ko -->
                            </p>
                        '''.format(
                            suggested=_(
                                "This password is automatically generated. "
                                "Please copy it or create your own. It will "
                                "not be shown again."
                            ),
                            strong=_("Good Job! Your password is strong!"),
                            almost=_("Your password is almost strong enough! Try adding numbers or symbols!"),
                            weak=_("Your password is too weak! Try adding numbers or symbols!"),
                            custom_warning=_(settings.CUSTOM_PASSWORD_STRENGTH_MESSAGE),
                            disabled_email=_(
                                "Setting a password is disabled. The user "
                                "will set their own password on confirming "
                                "their account email."
                            ),
                            disabled_phone=_(
                                "Setting a password is disabled. The user "
                                "will set their own password on confirming "
                                "their account phone number."
                            ),
                            short=_("Password must have at least {password_length} characters."
                                    ).format(password_length=settings.MINIMUM_PASSWORD_LENGTH)
                        )),
                        required=True,
                    ),
                    data_bind='''
                        css: {
                            'has-success': $root.passwordStatus() === $root.STATUS.SUCCESS,
                            'has-warning': $root.passwordStatus() === $root.STATUS.WARNING,
                            'has-error': $root.passwordStatus() === $root.STATUS.ERROR,
                        }
                    ''' if not has_custom_clean_password() else ''
                ),
            )
        )

        if self.show_deactivate_after_date:
            self.helper.layout.append(
                Fieldset(
                    _("Auto-Deactivation Settings"),
                    crispy.Field(
                        'deactivate_after_date',
                        data_bind="value: deactivate_after_date",
                    ),
                )
            )

    def clean_email(self):
        clean_email = self.cleaned_data['email'].strip().lower()
        if clean_email:
            validate_email(clean_email)
        return clean_email

    def clean_location_id(self):
        location_id = self.cleaned_data['location_id']
        if not user_can_access_location_id(self.domain, self.request_user, location_id):
            raise forms.ValidationError("You do not have access to that location.")
        if location_id:
            if not SQLLocation.active_objects.filter(domain=self.domain, location_id=location_id).exists():
                raise forms.ValidationError(_("This location does not exist"))
        return location_id

    def clean_username(self):
        username = self.cleaned_data['username']
        if username == 'admin' or username == 'demo_user':
            raise forms.ValidationError("The username %s is reserved for CommCare." % username)
        return clean_mobile_worker_username(self.domain, username)

    def clean_new_password(self):
        cleaned_password = self.cleaned_data.get('new_password')
        if self.project.strong_mobile_passwords:
            return clean_password(cleaned_password)
        return cleaned_password

    def clean_deactivate_after_date(self):
        return clean_deactivate_after_date(self.cleaned_data['deactivate_after_date'])


class GroupMembershipForm(forms.Form):
    selected_ids = forms.Field(
        label=gettext_lazy("Group Membership"),
        required=False,
        widget=Select2Ajax(multiple=True),
    )

    def __init__(self, group_api_url, *args, **kwargs):
        submit_label = kwargs.pop('submit_label', "Update")
        fieldset_title = kwargs.pop(
            'fieldset_title', gettext_lazy("Edit Group Membership"))

        super(GroupMembershipForm, self).__init__(*args, **kwargs)
        self.fields['selected_ids'].widget.set_url(group_api_url)

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                fieldset_title,
                'selected_ids',
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    Submit('submit', submit_label)
                )
            )
        )


class MultipleSelectionForm(forms.Form):
    """
    Form for selecting groups (used by the group UI on the user page)
    Usage::

        # views.py
        @property
        @memoized
        def users_form(self):
            form = MultipleSelectionForm(
                initial={'selected_ids': self.users_at_location},
                submit_label=_("Update Users at this Location"),
            )
            form.fields['selected_ids'].choices = self.all_users
            return form

        <form class="form disable-on-submit" id="edit_users" action="" method='post'>
            <legend>{% trans 'Specify Users At This Location' %}</legend>
            {% crispy users_per_location_form %}
        </form>

        @use_multiselect
        def dispatch(self, request, *args, **kwargs):
            return super(MyView, self).dispatch(request, *args, **kwargs)

        # javascript
        hqDefine("app/js/module", function() {
            // Multiselect widget
            $(function () {
                var multiselect_utils = hqImport('hqwebapp/js/multiselect_utils');
                multiselect_utils.createFullMultiselectWidget('id_of_multiselect_field', {
                    selectableHeaderTitle: gettext("Available Things"),
                    selectedHeaderTitle: gettext("Things Selected"),
                    searchItemTitle: gettext("Search Things..."),
                });
            });
        });
    """
    selected_ids = forms.MultipleChoiceField(
        label=gettext_lazy("Group Membership"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        submit_label = kwargs.pop('submit_label', "Update")
        fieldset_title = kwargs.pop('fieldset_title', gettext_lazy("Edit Group Membership"))

        super(MultipleSelectionForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-scheduledReportForm'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                fieldset_title,
                crispy.Field('selected_ids', css_class="hide"),
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    Submit('submit', submit_label)
                )
            )
        )


class PrimaryLocationWidget(forms.Widget):
    """
    Options for this field are dynamically set in JS depending on what options are selected
    for 'assigned_locations'. This works in conjunction with LocationSelectWidget.
    """

    def __init__(self, css_id, source_css_id, attrs=None):
        """
        args:
            css_id: css_id of primary_location field
            source_css_id: css_id of assigned_locations field
        """
        super(PrimaryLocationWidget, self).__init__(attrs)
        self.css_id = css_id
        self.source_css_id = source_css_id
        self.template = 'locations/manage/partials/drilldown_location_widget.html'

    def render(self, name, value, attrs=None, renderer=None):
        initial_data = {}
        if value:
            try:
                loc = SQLLocation.objects.get(location_id=value)
                initial_data = {
                    'id': loc.location_id,
                    'text': loc.get_path_display(),
                }
            except SQLLocation.DoesNotExist:
                pass

        return get_template(self.template).render({
            'css_id': self.css_id,
            'source_css_id': self.source_css_id,
            'name': name,
            'value': value,
            'initial_data': initial_data,
            'attrs': self.build_attrs(self.attrs, attrs),
        })


class CommtrackUserForm(forms.Form):
    assigned_locations = forms.CharField(
        label=gettext_noop("Locations"),
        required=False,
        widget=forms.SelectMultiple(choices=[]),
    )
    primary_location = forms.CharField(
        label=gettext_noop("Primary Location"),
        required=False,
        help_text=gettext_lazy('Primary Location must always be set to one of above locations')
    )
    program_id = forms.ChoiceField(
        label=gettext_noop("Program"),
        choices=(),
        required=False
    )

    def __init__(self, *args, **kwargs):
        from corehq.apps.locations.forms import LocationSelectWidget
        self.request = kwargs.pop('request')
        self.domain = kwargs.pop('domain', None)
        super(CommtrackUserForm, self).__init__(*args, **kwargs)
        self.fields['assigned_locations'].widget = LocationSelectWidget(
            self.domain, multiselect=True, id='id_assigned_locations'
        )
        self.fields['assigned_locations'].help_text = ExpandedMobileWorkerFilter.location_search_help
        self.fields['primary_location'].widget = PrimaryLocationWidget(
            css_id='id_primary_location',
            source_css_id='id_assigned_locations',
        )
        if self.commtrack_enabled:
            programs = Program.by_domain(self.domain)
            choices = list((prog.get_id, prog.name) for prog in programs)
            choices.insert(0, ('', ''))
            self.fields['program_id'].choices = choices
        else:
            self.fields['program_id'].widget = forms.HiddenInput()

        self.helper = FormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

    @property
    @memoized
    def commtrack_enabled(self):
        return Domain.get_by_name(self.domain).commtrack_enabled

    def save(self, user):
        # todo: Avoid multiple user.save
        user_change_logger = UserChangeLogger(
            upload_domain=self.domain,
            user_domain=self.domain,
            user=user,
            is_new_user=False,
            changed_by_user=self.request.couch_user,
            changed_via=USER_CHANGE_VIA_WEB,
            upload_record_id=None,
        )
        updated_program_id = None
        domain_membership = user.get_domain_membership(self.domain)
        if self.commtrack_enabled:
            program_id = self.cleaned_data['program_id']
            if domain_membership.program_id != program_id:
                updated_program_id = program_id
            domain_membership.program_id = program_id

        location_updates = self._update_location_data(user)
        if user.is_commcare_user():
            self._log_commcare_user_changes(user_change_logger, location_updates, updated_program_id)
        else:
            self._log_web_user_changes(user_change_logger, location_updates, updated_program_id)

    def _update_location_data(self, user):
        new_location_id = self.cleaned_data['primary_location']
        new_location_ids = self.cleaned_data['assigned_locations']
        updates = {}

        if user.is_commcare_user():
            # fetch this before set_location is called
            old_assigned_location_ids = set(user.assigned_location_ids)
            old_location_id = user.location_id
            if new_location_id != old_location_id:
                if new_location_id:
                    user.set_location(SQLLocation.objects.get(location_id=new_location_id))
                else:
                    user.unset_location()

            old_location_ids = user.assigned_location_ids
            if set(new_location_ids) != set(old_location_ids):
                user.reset_locations(new_location_ids)
            if old_assigned_location_ids != set(new_location_ids):
                updates['location_ids'] = new_location_ids
        else:
            domain_membership = user.get_domain_membership(self.domain)
            # fetch this before set_location is called
            old_assigned_location_ids = set(domain_membership.assigned_location_ids)
            old_location_id = domain_membership.location_id
            if new_location_id != old_location_id:
                if new_location_id:
                    user.set_location(self.domain, SQLLocation.objects.get(location_id=new_location_id))
                else:
                    user.unset_location(self.domain)

            old_location_ids = domain_membership.assigned_location_ids
            if set(new_location_ids) != set(old_location_ids):
                user.reset_locations(self.domain, new_location_ids)
            if old_assigned_location_ids != set(new_location_ids):
                updates['location_ids'] = new_location_ids

        # check for this post reset_locations which can also update location_id
        new_primary_location = user.get_sql_location(self.domain)
        if new_primary_location and old_location_id != new_primary_location.location_id:
            updates['location_id'] = new_location_id
        elif old_location_id and not new_primary_location:
            updates['location_id'] = None
        return updates

    def _log_commcare_user_changes(self, user_change_logger, location_updates, program_id):
        if 'location_ids' in location_updates:
            location_ids = location_updates['location_ids']
            user_change_logger.add_changes({'assigned_location_ids': location_ids})
            if location_ids:
                locations = SQLLocation.objects.filter(location_id__in=location_ids)
                user_change_logger.add_info(
                    UserChangeMessage.assigned_locations_info(locations)
                )
            else:
                user_change_logger.add_info(
                    UserChangeMessage.assigned_locations_info([])
                )

        if 'location_id' in location_updates:
            location_id = location_updates['location_id']
            user_change_logger.add_changes({'location_id': location_id})
            if location_id:
                primary_location = SQLLocation.objects.get(location_id=location_id)
                user_change_logger.add_info(
                    UserChangeMessage.primary_location_info(primary_location)
                )
            else:
                user_change_logger.add_info(UserChangeMessage.primary_location_removed())

        if program_id is not None:
            self._log_program_changes(user_change_logger, program_id)
        user_change_logger.save()

    @staticmethod
    def _log_program_changes(user_change_logger, program_id):
        if program_id:
            program = Program.get(program_id)
            user_change_logger.add_info(UserChangeMessage.program_change(program))
        else:
            user_change_logger.add_info(UserChangeMessage.program_change(None))

    def _log_web_user_changes(self, user_change_logger, location_updates, program_id):
        if 'location_ids' in location_updates:
            location_ids = location_updates['location_ids']
            if location_ids:
                locations = SQLLocation.objects.filter(location_id__in=location_ids)
                user_change_logger.add_info(
                    UserChangeMessage.assigned_locations_info(locations)
                )
            else:
                user_change_logger.add_info(
                    UserChangeMessage.assigned_locations_info([])
                )

        if 'location_id' in location_updates:
            location_id = location_updates['location_id']
            if location_id:
                primary_location = SQLLocation.objects.get(location_id=location_id)
                user_change_logger.add_info(
                    UserChangeMessage.primary_location_info(primary_location)
                )
            else:
                user_change_logger.add_info(
                    UserChangeMessage.primary_location_removed()
                )

        if program_id is not None:
            self._log_program_changes(user_change_logger, program_id)

        user_change_logger.save()

    def clean_assigned_locations(self):
        from corehq.apps.locations.models import SQLLocation
        from corehq.apps.locations.util import get_locations_from_ids

        location_ids = self.data.getlist('assigned_locations')
        try:
            locations = get_locations_from_ids(location_ids, self.domain)
        except SQLLocation.DoesNotExist:
            raise ValidationError(_('One or more of the locations was not found.'))

        return [location.location_id for location in locations]

    def clean(self):
        cleaned_data = super(CommtrackUserForm, self).clean()

        primary_location_id = cleaned_data['primary_location']
        assigned_location_ids = cleaned_data.get('assigned_locations', [])
        if primary_location_id:
            if primary_location_id not in assigned_location_ids:
                self.add_error(
                    'primary_location',
                    _("Primary location must be one of the user's locations")
                )
        if assigned_location_ids and not primary_location_id:
            self.add_error(
                'primary_location',
                _("Primary location can't be empty if the user has any "
                  "locations set")
            )


class DomainRequestForm(forms.Form):
    full_name = forms.CharField(label=gettext_lazy('Full Name'), required=True,
                                widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.CharField(
        label=gettext_lazy('Email Address'),
        required=True,
        help_text=gettext_lazy('You will use this email to log in.'),
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    domain = forms.CharField(widget=forms.HiddenInput(), required=True)

    @property
    def form_actions(self):
        return hqcrispy.FormActions(
            twbscrispy.StrictButton(
                gettext_lazy('Request Access'),
                type='submit',
                css_class='btn-primary',
            )
        )

    def __init__(self, *args, **kwargs):
        super(DomainRequestForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-6 col-md-5 col-lg-3'
        self.helper.show_form_errors = True
        self.helper.layout = crispy.Layout(
            'full_name',
            'email',
            'domain',
            self.form_actions,
        )

    def clean_email(self):
        data = self.cleaned_data['email'].strip().lower()
        validate_email(data)
        return data


class ConfirmExtraUserChargesForm(EditBillingAccountInfoForm):
    def __init__(self, account, domain, creating_user, data=None, *args, **kwargs):
        super(ConfirmExtraUserChargesForm, self).__init__(
            account, domain, creating_user, data=data, *args, **kwargs)

        from corehq.apps.users.views.mobile import MobileWorkerListView
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Basic Information"),
                'company_name',
                'first_name',
                'last_name',
                crispy.Field('email_list', css_class='input-xxlarge accounting-email-select2',
                             data_initial=json.dumps(self.initial.get('email_list'))),
                'phone_number',
            ),
            crispy.Fieldset(
                _("Mailing Address"),
                'first_line',
                'second_line',
                'city',
                'state_province_region',
                'postal_code',
                crispy.Field('country', css_class="input-large accounting-country-select2",
                             data_country_code=self.current_country or '',
                             data_country_name=COUNTRIES.get(self.current_country, '')),
            ),
            hqcrispy.FormActions(
                crispy.HTML(
                    '<a href="%(user_list_url)s" class="btn btn-default">%(text)s</a>' % {
                        'user_list_url': reverse(MobileWorkerListView.urlname, args=[self.domain]),
                        'text': _("Back to Mobile Workers List")
                    }
                ),
                StrictButton(
                    _("Confirm Billing Information"),
                    type="submit",
                    css_class='btn btn-primary disabled',
                ),
            ),
        )

    def save(self, commit=True):
        account_save_success = super(ConfirmExtraUserChargesForm, self).save(commit=False)
        if not account_save_success:
            return False
        self.account.date_confirmed_extra_charges = datetime.datetime.today()
        self.account.save()
        return True


class AddPhoneNumberForm(forms.Form):
    phone_number = forms.CharField(
        max_length=50, help_text=gettext_lazy('Please enter number, including country code, in digits only.')
    )

    form_type = forms.CharField(initial='add-phonenumber', widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super(AddPhoneNumberForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            Fieldset(
                _('Add a Phone Number'),
                'form_type',
                twbscrispy.PrependedText('phone_number', '+', type='tel', pattern=r'\d+')
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _('Add Number'),
                    css_class='btn-primary disable-on-submit',
                    type='submit',
                )
            )
        )
        self.fields['phone_number'].label = gettext_lazy('Phone number')


class CommCareUserFormSet(object):
    """Combines the CommCareUser form and the Custom Data form"""

    def __init__(self, domain, editable_user, request_user, request, data=None, *args, **kwargs):
        self.domain = domain
        self.editable_user = editable_user
        self.request_user = request_user
        self.request = request
        self.data = data
        self.loadtest_users_enabled = domain_has_privilege(
            domain,
            privileges.LOADTEST_USERS,
        )

    @property
    @memoized
    def user_form(self):
        return UpdateCommCareUserInfoForm(
            data=self.data, domain=self.domain, existing_user=self.editable_user, request=self.request)

    @property
    @memoized
    def action_form(self):
        return CommCareUserActionForm(
            data=self.data,
            domain=self.domain,
            existing_user=self.editable_user,
            request=self.request,
        )

    @property
    @memoized
    def custom_data(self):
        from corehq.apps.users.views.mobile.custom_data_fields import (
            UserFieldsView,
        )
        return CustomDataEditor(
            domain=self.domain,
            field_view=UserFieldsView,
            existing_custom_data=self.editable_user.get_user_data(self.domain).to_dict(),
            post_dict=self.data,
            ko_model="custom_fields",
        )

    def is_valid(self):
        return (self.data is not None
                and all([self.user_form.is_valid(), self.custom_data.is_valid()]))

    def update_user(self):
        user_data = self.user_form.existing_user.get_user_data(self.domain)
        old_profile_id = user_data.profile_id
        new_user_data = self.custom_data.get_data_to_save()
        new_profile_id = new_user_data.pop(PROFILE_SLUG, ...)
        changed = user_data.update(new_user_data, new_profile_id)
        return self.user_form.update_user(
            metadata_updated=changed,
            profile_updated=old_profile_id != new_profile_id
        )


class UserFilterForm(forms.Form):
    USERNAMES_COLUMN_OPTION = 'usernames'
    COLUMNS_CHOICES = (
        ('all', gettext_noop('All')),
        (USERNAMES_COLUMN_OPTION, gettext_noop('Only Usernames'))
    )
    ACTIVE = 'active'
    INACTIVE = 'inactive'

    USER_ACTIVE_STATUS = [
        ('show_all', gettext_lazy('Show All')),
        (ACTIVE, gettext_lazy('Only Active')),
        (INACTIVE, gettext_lazy('Only Deactivated'))
    ]

    role_id = forms.ChoiceField(label=gettext_lazy('Role'), choices=(), required=False)
    search_string = forms.CharField(
        label=gettext_lazy('Name or Username'),
        max_length=30,
        required=False
    )
    location_id = forms.CharField(
        label=gettext_noop("Location"),
        required=False,
    )
    selected_location_only = forms.BooleanField(
        required=False,
        label=_('Only include mobile workers at the selected location'),
    )
    user_active_status = forms.ChoiceField(
        label=_('Active / Deactivated'),
        choices=USER_ACTIVE_STATUS,
        required=False,
        widget=SelectToggle(choices=USER_ACTIVE_STATUS, attrs={'ko_value': 'user_active_status'}),
    )
    columns = forms.ChoiceField(
        required=False,
        label=gettext_noop("Columns"),
        choices=COLUMNS_CHOICES,
        widget=SelectToggle(choices=COLUMNS_CHOICES, attrs={'ko_value': 'columns'}),
    )
    domains = forms.MultipleChoiceField(
        required=False,
        label=_('Project Spaces'),
        widget=forms.SelectMultiple(attrs={'class': 'hqwebapp-select2'}),
    )

    def __init__(self, *args, **kwargs):
        from corehq.apps.locations.forms import LocationSelectWidget
        self.domain = kwargs.pop('domain')
        self.couch_user = kwargs.pop('couch_user')
        self.user_type = kwargs.pop('user_type')
        if self.user_type not in [MOBILE_USER_TYPE, WEB_USER_TYPE]:
            raise AssertionError(f"Invalid user type for UserFilterForm: {self.user_type}")
        super().__init__(*args, **kwargs)

        self.fields['location_id'].widget = LocationSelectWidget(
            self.domain,
            id='id_location_id',
            placeholder=_("All Locations"),
            attrs={'data-bind': 'value: location_id'},
        )
        self.fields['location_id'].widget.query_url = "{url}?show_all=true".format(
            url=self.fields['location_id'].widget.query_url
        )

        self.fields['location_id'].help_text = ExpandedMobileWorkerFilter.location_search_help

        roles = UserRole.objects.get_by_domain(self.domain)
        self.fields['role_id'].choices = [('', _('All Roles'))] + [
            (role.get_id, role.name or _('(No Name)')) for role in roles
            if not role.is_commcare_user_default
        ]

        subdomains = EnterprisePermissions.get_domains(self.domain)
        self.fields['domains'].choices = [('all_project_spaces', _('All Project Spaces'))] + \
                                         [(self.domain, self.domain)] + \
                                         [(domain, domain) for domain in subdomains]

        self.helper = FormHelper()
        self.helper.form_method = 'GET'
        self.helper.form_id = 'user-filters'
        self.helper.form_class = 'form-horizontal'
        view_name = 'download_commcare_users' if self.user_type == MOBILE_USER_TYPE else 'download_web_users'
        self.helper.form_action = reverse(view_name, args=[self.domain])

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_text_inline = True

        fields = []
        if subdomains:
            fields += [crispy.Field("domains", data_bind="value: domains")]
        fields += [
            crispy.Div(
                crispy.Field(
                    "role_id",
                    css_class="hqwebapp-select2",
                    data_bind="value: role_id",
                ),
                data_bind="slideVisible: !isCrossDomain()",
            ),
            crispy.Field("search_string", data_bind="value: search_string"),
            crispy.Div(
                "location_id",
                data_bind="slideVisible: !isCrossDomain()",
            ),
            crispy.Div(
                crispy.Field(
                    "selected_location_only",
                    data_bind="checked: selected_location_only"
                ),
                data_bind="slideVisible: !isCrossDomain() && location_id",
            )
        ]

        fieldset_label = _('Filter and Download Users')
        if self.user_type == MOBILE_USER_TYPE:
            fieldset_label = _('Filter and Download Mobile Workers')
            fields += [
                "user_active_status",
                crispy.Field("columns", data_bind="value: columns"),
            ]

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                fieldset_label,
                *fields,
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Download"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
                crispy.Div(
                    data_bind="template: {name: 'ko-template-download-statistics'}",
                    style="display: inline;",
                )
            ),
        )

    def clean_role_id(self):
        role_id = self.cleaned_data['role_id']
        if not role_id:
            return None

        try:
            UserRole.objects.by_couch_id(role_id, domain=self.domain)
        except UserRole.DoesNotExist:
            raise forms.ValidationError(_("Invalid Role"))
        return role_id

    def clean_search_string(self):
        search_string = self.cleaned_data['search_string']
        if "*" in search_string or "?" in search_string:
            raise forms.ValidationError(_("* and ? are not allowed"))
        return search_string

    def clean_domains(self):
        if 'domains' in self.data:
            domains = self.data.getlist('domains')
        else:
            domains = self.data.getlist('domains[]', [self.domain])

        if 'all_project_spaces' in domains:
            domains = EnterprisePermissions.get_domains(self.domain)
            domains += [self.domain]
        return sorted(domains)

    def clean_user_active_status(self):
        user_active_status = self.cleaned_data['user_active_status']

        if user_active_status == self.ACTIVE:
            return True
        if user_active_status == self.INACTIVE:
            return False
        return None

    def clean(self):
        data = self.cleaned_data
        user = self.couch_user

        if not user.has_permission(self.domain, 'access_all_locations') and not data.get('location_id'):
            # Add (web) user assigned_location_ids so as to
            # 1) reflect all locations user is assigned to ('All' option)
            # 2) restrict user access
            domain_membership = user.get_domain_membership(self.domain)
            if domain_membership and domain_membership.assigned_location_ids:
                data['web_user_assigned_location_ids'] = list(domain_membership.assigned_location_ids)

        return data


class TableauUserForm(forms.Form):
    role = forms.ChoiceField(
        label=gettext_noop("Role"),
        choices=TableauUser.Roles.choices,
        required=True,
    )
    groups = forms.MultipleChoiceField(
        label=gettext_noop("Groups"),
        choices=[],
        required=False,
        widget=forms.CheckboxSelectMultiple()
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        self.domain = kwargs.pop('domain', None)
        self.username = kwargs.pop('username', None)
        super(TableauUserForm, self).__init__(*args, **kwargs)

        self.allowed_tableau_groups = [
            TableauGroupTuple(group.name, group.id) for group in get_all_tableau_groups(self.domain)
            if group.name in get_allowed_tableau_groups_for_domain(self.domain)]
        user_group_names = [group.name for group in get_tableau_groups_for_user(self.domain, self.username)]
        self.fields['groups'].choices = []
        self.fields['groups'].initial = []
        for i, group in enumerate(self.allowed_tableau_groups):
            # Add a choice for each tableau group on the server
            self.fields['groups'].choices.append((i, group.name))
            if group.name in user_group_names:
                # Pre-choose groups that the user already belongs to
                self.fields['groups'].initial.append(i)
        if not self.fields['groups'].choices:
            del self.fields['groups']

        self.helper = FormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

    def save(self, username, commit=True):
        groups = [self.allowed_tableau_groups[int(i)] for i in self.cleaned_data['groups']]
        update_tableau_user(self.domain, username, self.cleaned_data['role'], groups)
