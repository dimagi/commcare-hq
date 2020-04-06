import datetime
import json
import re

from django import forms
from django.conf import settings
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, validate_email
from django.forms.widgets import PasswordInput
from django.template.loader import get_template
from django.urls import reverse
from django.utils.functional import lazy
from django.utils.safestring import mark_safe
from django.utils.text import format_lazy
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy, ugettext_noop

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout, Submit
from django_countries.data import COUNTRIES
from memoized import memoized

from corehq.toggles import TWO_STAGE_USER_PROVISIONING
from dimagi.utils.django.fields import TrimmedCharField

from corehq import toggles
from corehq.apps.analytics.tasks import set_analytics_opt_out
from corehq.apps.app_manager.models import validate_lang
from corehq.apps.custom_data_fields.edit_entity import CustomDataEditor
from corehq.apps.domain.forms import EditBillingAccountInfoForm, clean_password
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import HQModalFormHelper
from corehq.apps.hqwebapp.utils import decode_password
from corehq.apps.hqwebapp.widgets import (
    Select2Ajax,
    SelectToggle,
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import user_can_access_location_id
from corehq.apps.programs.models import Program
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.users.models import CouchUser, UserRole
from corehq.apps.users.util import cc_user_domain, format_username
from custom.nic_compliance.forms import EncodedPasswordChangeFormMixin

mark_safe_lazy = lazy(mark_safe, str)

UNALLOWED_MOBILE_WORKER_NAMES = ('admin', 'demo_user')


def get_mobile_worker_max_username_length(domain):
    """
    The auth_user table only allows for usernames up to 128 characters long.
    The code used to allow for usernames up to 80 characters, but that
    didn't properly take into consideration the fact that the domain and
    site name vary.
    """
    return min(128 - len(cc_user_domain(domain)) - 1, 80)


def clean_mobile_worker_username(domain, username, name_too_long_message=None,
        name_reserved_message=None, name_exists_message=None):

    max_username_length = get_mobile_worker_max_username_length(domain)

    if len(username) > max_username_length:
        raise forms.ValidationError(name_too_long_message or
            _('Username %(username)s is too long.  Must be under %(max_length)s characters.')
            % {'username': username, 'max_length': max_username_length})

    if username in UNALLOWED_MOBILE_WORKER_NAMES:
        raise forms.ValidationError(name_reserved_message or
            _('The username "%(username)s" is reserved for CommCare.')
            % {'username': username})

    username = format_username(username, domain)
    validate_username(username)

    if CouchUser.username_exists(username):
        raise forms.ValidationError(name_exists_message or
            _('This Mobile Worker already exists.'))

    return username


def wrapped_language_validation(value):
    try:
        validate_lang(value)
    except ValueError:
        raise forms.ValidationError("%s is not a valid language code! Please "
                                    "enter a valid two or three digit code." % value)


def generate_strong_password():
    import string
    import random
    possible = string.punctuation + string.ascii_lowercase + string.ascii_uppercase + string.digits
    password = ''
    password += random.choice(string.punctuation)
    password += random.choice(string.ascii_lowercase)
    password += random.choice(string.ascii_uppercase)
    password += random.choice(string.digits)
    password += ''.join(random.choice(possible) for i in range(random.randrange(6, 11)))

    return ''.join(random.sample(password, len(password)))


class LanguageField(forms.CharField):
    """
    Adds language code validation to a field
    """

    def __init__(self, *args, **kwargs):
        super(LanguageField, self).__init__(*args, **kwargs)
        self.min_length = 2
        self.max_length = 3

    default_error_messages = {
        'invalid': ugettext_lazy('Please enter a valid two or three digit language code.'),
    }
    default_validators = [wrapped_language_validation]


class BaseUpdateUserForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain')
        self.existing_user = kwargs.pop('existing_user')
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

        for prop in self.direct_properties:
            setattr(self.existing_user, prop, self.cleaned_data[prop])
            is_update_successful = True

        if is_update_successful and save:
            self.existing_user.save()
        return is_update_successful


class UpdateUserRoleForm(BaseUpdateUserForm):
    role = forms.ChoiceField(choices=(), required=False)

    def update_user(self):
        is_update_successful = super(UpdateUserRoleForm, self).update_user(save=False)

        if self.domain and 'role' in self.cleaned_data:
            role = self.cleaned_data['role']
            try:
                self.existing_user.set_role(self.domain, role)
                if self.existing_user.is_commcare_user():
                    self.existing_user.save(spawn_task=True)
                else:
                    self.existing_user.save()
                is_update_successful = True
            except KeyError:
                pass
        elif is_update_successful:
            self.existing_user.save()

        return is_update_successful

    def load_roles(self, role_choices=None, current_role=None):
        if role_choices is None:
            role_choices = []
        self.fields['role'].choices = role_choices

        if current_role:
            self.initial['role'] = current_role


class UpdateUserPermissionForm(forms.Form):
    super_user = forms.BooleanField(label=ugettext_lazy('System Super User'), required=False)

    def update_user_permission(self, couch_user=None, editable_user=None, is_super_user=None):
        is_update_successful = False
        if editable_user and couch_user.is_superuser:
            editable_user.is_superuser = is_super_user
            editable_user.save()
            is_update_successful = True

        return is_update_successful


class BaseUserInfoForm(forms.Form):
    first_name = forms.CharField(label=ugettext_lazy('First Name'), max_length=30, required=False)
    last_name = forms.CharField(label=ugettext_lazy('Last Name'), max_length=30, required=False)
    email = forms.EmailField(label=ugettext_lazy("E-Mail"), max_length=75, required=False)
    language = forms.ChoiceField(
        choices=(),
        initial=None,
        required=False,
        help_text=mark_safe_lazy(
            ugettext_lazy(
                "<i class=\"fa fa-info-circle\"></i> "
                "Becomes default language seen in Web Apps and reports (if applicable), "
                "but does not affect mobile applications. "
                "Supported languages for reports are en, fr (partial), and hin (partial)."
            )
        )
    )

    def load_language(self, language_choices=None):
        if language_choices is None:
            language_choices = []
        self.fields['language'].choices = [('', '')] + language_choices


class UpdateMyAccountInfoForm(BaseUpdateUserForm, BaseUserInfoForm):
    analytics_enabled = forms.BooleanField(
        required=False,
        label=ugettext_lazy("Enable Tracking"),
        help_text=ugettext_lazy(
            "Allow Dimagi to collect usage information to improve CommCare. "
            "You can learn more about the information we collect and the ways "
            "we use it in our "
            '<a href="http://www.dimagi.com/terms/latest/privacy/">privacy policy</a>'
        ),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs['existing_user']
        api_key = kwargs.pop('api_key') if 'api_key' in kwargs else None
        super(UpdateMyAccountInfoForm, self).__init__(*args, **kwargs)
        self.username = self.user.username

        username_controls = []
        if self.username:
            username_controls.append(hqcrispy.StaticField(
                ugettext_lazy('Username'), self.username)
            )

        api_key_controls = [
            hqcrispy.StaticField(ugettext_lazy('API Key'), api_key),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    ugettext_lazy('Generate API Key'),
                    type="button",
                    id='generate-api-key',
                    css_class='btn-default',
                ),
                css_class="form-group"
            ),
        ]

        self.fields['language'].label = ugettext_lazy("My Language")

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
            hqcrispy.Field('first_name'),
            hqcrispy.Field('last_name'),
            hqcrispy.Field('email'),
        ]
        if self.set_analytics_enabled:
            basic_fields.append(twbscrispy.PrependedText('analytics_enabled', ''),)

        self.new_helper.layout = crispy.Layout(
            crispy.Fieldset(
                ugettext_lazy("Basic"),
                *basic_fields
            ),
            (hqcrispy.FieldsetAccordionGroup if self.collapse_other_options else crispy.Fieldset)(
                ugettext_lazy("Other Options"),
                hqcrispy.Field('language'),
                crispy.Div(*api_key_controls),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    ugettext_lazy("Update My Information"),
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
    loadtest_factor = forms.IntegerField(
        required=False, min_value=1, max_value=50000,
        help_text=ugettext_lazy(
            "Multiply this user's case load by a number for load testing on phones. "
            "Leave blank for normal users."
        ),
        widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super(UpdateCommCareUserInfoForm, self).__init__(*args, **kwargs)
        self.fields['role'].help_text = _(mark_safe(
            '<i class="fa fa-info-circle"></i> '
            'Only applies to mobile workers who will be entering data using '
            '<a href="https://wiki.commcarehq.org/display/commcarepublic/Web+Apps">'
            'Web Apps</a>'
        ))
        if toggles.ENABLE_LOADTEST_USERS.enabled(self.domain):
            self.fields['loadtest_factor'].widget = forms.TextInput()

    @property
    def direct_properties(self):
        indirect_props = ['role']
        return [k for k in self.fields if k not in indirect_props]


class RoleForm(forms.Form):

    def __init__(self, *args, **kwargs):
        if 'role_choices' in kwargs:
            role_choices = kwargs.pop('role_choices')
        else:
            role_choices = ()
        super(RoleForm, self).__init__(*args, **kwargs)
        self.fields['role'].choices = role_choices


class SetUserPasswordForm(EncodedPasswordChangeFormMixin, SetPasswordForm):

    new_password1 = forms.CharField(
        label=ugettext_noop("New password"),
        widget=forms.PasswordInput(),
    )

    def __init__(self, project, user_id, **kwargs):
        super(SetUserPasswordForm, self).__init__(**kwargs)
        self.project = project
        initial_password = ''

        if self.project.strong_mobile_passwords:
            self.fields['new_password1'].widget = forms.TextInput()
            self.fields['new_password1'].help_text = mark_safe_lazy(
                format_lazy(
                    ('<i class="fa fa-warning"></i>{}<br />'
                     '<span data-bind="text: passwordHelp, css: color">'),
                    ugettext_lazy(
                        "This password is automatically generated. "
                        "Please copy it or create your own. It will not be shown again."),
                )
            )
            initial_password = generate_strong_password()

        self.helper = FormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_tag = False

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_action = reverse("change_password", args=[project.name, user_id])
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
                hqcrispy.FormActions(
                    crispy.ButtonHolder(
                        Submit('submit', _('Reset Password'))
                    )
                ),
                css_class="check-password",
            ),
        )

    def clean_new_password1(self):
        password1 = decode_password(self.cleaned_data.get('new_password1'))
        if password1 == '':
            raise ValidationError(
                _("Password cannot be empty"), code='new_password1_empty',
            )
        if self.project.strong_mobile_passwords:
            return clean_password(password1)
        return password1


class CommCareAccountForm(forms.Form):
    """
    Form for CommCareAccounts
    """
    username = forms.CharField(required=True)
    password_1 = forms.CharField(label=ugettext_lazy('Password'), widget=PasswordInput(),
                                 required=True, min_length=1)
    password_2 = forms.CharField(label=ugettext_lazy('Password (reenter)'), widget=PasswordInput(),
                                 required=True, min_length=1)
    phone_number = forms.CharField(
        max_length=80,
        required=False,
        help_text=ugettext_lazy("Please enter number, including "
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

validate_username = EmailValidator(message=ugettext_lazy('Username contains invalid characters.'))


class NewMobileWorkerForm(forms.Form):
    username = forms.CharField(
        max_length=50,
        required=True,
        help_text="""
            <span data-bind="visible: $root.usernameAvailabilityStatus() !== $root.STATUS.NONE">
                <i class="fa fa-circle-o-notch fa-spin"
                   data-bind="visible: $root.usernameAvailabilityStatus() === $root.STATUS.PENDING"></i>
                <i class="fa fa-check"
                   data-bind="visible: $root.usernameAvailabilityStatus() === $root.STATUS.SUCCESS"></i>
                <i class="fa fa-exclamation-triangle"
                   data-bind="visible: $root.usernameAvailabilityStatus() === $root.STATUS.WARNING ||
                                       $root.usernameAvailabilityStatus() === $root.STATUS.ERROR"></i>
                <!-- ko text: $root.usernameStatusMessage --><!-- /ko -->
            </span>
        """,
        label=ugettext_noop("Username"),
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        label=ugettext_noop("First Name"),
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        label=ugettext_noop("Last Name")
    )
    location_id = forms.CharField(
        label=ugettext_noop("Location"),
        required=False,
    )
    force_account_confirmation = forms.BooleanField(
        label=ugettext_noop("Require Account Confirmation?"),
        help_text=ugettext_noop(
            "The user's account will not be active until "
            "they have confirmed their email and set a password."
        ),
        required=False,
    )
    email = forms.EmailField(
        label=ugettext_noop("Email"),
        required=False,
        help_text="""
            <span data-bind="visible: $root.emailStatus() !== $root.STATUS.NONE">
                <i class="fa fa-exclamation-triangle"
                   data-bind="visible: $root.emailStatus() === $root.STATUS.ERROR"></i>
                <!-- ko text: $root.emailStatusMessage --><!-- /ko -->
            </span>
        """
    )
    send_account_confirmation_email = forms.BooleanField(
        label=ugettext_noop("Send Account Confirmation Email Now?"),
        help_text=ugettext_noop(
            "The user will be sent their account confirmation email now. "
            "Otherwise it must be sent manually from the Mobile Worker 'Deactivated Users' list."
        ),
        required=False,
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(),
        required=True,
        min_length=1,
        label=ugettext_noop("Password"),
    )

    def __init__(self, project, request_user, *args, **kwargs):
        super(NewMobileWorkerForm, self).__init__(*args, **kwargs)
        email_string = "@{}.{}".format(project.name, settings.HQ_ACCOUNT_ROOT)
        max_chars_username = 80 - len(email_string)
        self.project = project
        self.domain = self.project.name
        self.request_user = request_user
        self.can_access_all_locations = request_user.has_permission(self.domain, 'access_all_locations')
        if not self.can_access_all_locations:
            self.fields['location_id'].required = True

        if self.project.strong_mobile_passwords:
            # Use normal text input so auto-generated strong password is visible
            self.fields['new_password'].widget = forms.TextInput()
            self.fields['new_password'].help_text = mark_safe_lazy(
                format_lazy(
                    '<i class="fa fa-warning"></i>{}<br />',
                    ugettext_lazy(
                        'This password is automatically generated. '
                        'Please copy it or create your own. It will not be shown again.'),
                )
            )

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
                                <!-- ko if: $root.passwordStatus() === $root.STATUS.SUCCESS -->
                                    <i class="fa fa-check"></i> {strong}
                                <!-- /ko -->
                                <!-- ko ifnot: $root.useDraconianSecurity() -->
                                    <!-- ko if: $root.passwordStatus() === $root.STATUS.WARNING -->
                                        {almost}
                                    <!-- /ko -->
                                    <!-- ko if: $root.passwordStatus() === $root.STATUS.ERROR -->
                                        <i class="fa fa-warning"></i> {weak}
                                    <!-- /ko -->
                                <!-- /ko -->

                                <!-- ko if: $root.useDraconianSecurity() -->
                                    <!-- ko if: $root.passwordStatus() === $root.STATUS.ERROR -->
                                        <i class="fa fa-warning"></i> {rules}
                                    <!-- /ko -->
                                <!-- /ko -->
                                <!-- ko if: $root.passwordStatus() === $root.STATUS.DISABLED -->
                                    <i class="fa fa-warning"></i> {disabled}
                                <!-- /ko -->
                            </p>
                        '''.format(
                            suggested=_("This password is automatically generated. Please copy it or create "
                                "your own. It will not be shown again."),
                            strong=_("Good Job! Your password is strong!"),
                            almost=_("Your password is almost strong enough! Try adding numbers or symbols!"),
                            weak=_("Your password is too weak! Try adding numbers or symbols!"),
                            rules=_("Password Requirements: 1 special character, 1 number, 1 capital letter, "
                                "minimum length of 8 characters."),
                            disabled=_("Setting a password is disabled. "
                                       "The user will set their own password on confirming their account email."),
                        )),
                        required=True,
                    ),
                    data_bind='''
                        css: {
                            'has-success': $root.passwordStatus() === $root.STATUS.SUCCESS,
                            'has-warning': $root.passwordStatus() === $root.STATUS.WARNING,
                            'has-error': $root.passwordStatus() === $root.STATUS.ERROR,
                        }
                    '''
                ),
            )
        )

    def clean_location_id(self):
        location_id = self.cleaned_data['location_id']
        if not user_can_access_location_id(self.domain, self.request_user, location_id):
            raise forms.ValidationError("You do not have access to that location.")
        return location_id

    def clean_username(self):
        username = self.cleaned_data['username']
        if username == 'admin' or username == 'demo_user':
            raise forms.ValidationError("The username %s is reserved for CommCare." % username)
        return clean_mobile_worker_username(self.domain, username)

    def clean_new_password(self):
        cleaned_password = decode_password(self.cleaned_data.get('new_password'))
        if self.project.strong_mobile_passwords:
            return clean_password(cleaned_password)
        return cleaned_password


class GroupMembershipForm(forms.Form):
    selected_ids = forms.Field(
        label=ugettext_lazy("Group Membership"),
        required=False,
        widget=Select2Ajax(multiple=True),
    )

    def __init__(self, group_api_url, *args, **kwargs):
        submit_label = kwargs.pop('submit_label', "Update")
        fieldset_title = kwargs.pop(
            'fieldset_title', ugettext_lazy("Edit Group Membership"))

        super(GroupMembershipForm, self).__init__(*args, **kwargs)
        self.fields['selected_ids'].widget.set_url(group_api_url)

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                fieldset_title,
                crispy.Field('selected_ids'),
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
                multiselect_utils.createFullMultiselectWidget(
                    'id_of_multiselect_field',
                    django.gettext("Available Things"),
                    django.gettext("Things Selected"),
                    django.gettext("Search Things...")
                );
            });
        });
    """
    selected_ids = forms.MultipleChoiceField(
        label=ugettext_lazy("Group Membership"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        submit_label = kwargs.pop('submit_label', "Update")
        fieldset_title = kwargs.pop('fieldset_title', ugettext_lazy("Edit Group Membership"))

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
        label=ugettext_noop("Locations"),
        required=False,
        widget=forms.SelectMultiple(choices=[]),
    )
    primary_location = forms.CharField(
        label=ugettext_noop("Primary Location"),
        required=False,
        help_text=ugettext_lazy('Primary Location must always be set to one of above locations')
    )
    program_id = forms.ChoiceField(
        label=ugettext_noop("Program"),
        choices=(),
        required=False
    )

    def __init__(self, *args, **kwargs):
        from corehq.apps.locations.forms import LocationSelectWidget
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
        domain_membership = user.get_domain_membership(self.domain)
        if self.commtrack_enabled:
            domain_membership.program_id = self.cleaned_data['program_id']

        self._update_location_data(user)

    def _update_location_data(self, user):
        location_id = self.cleaned_data['primary_location']
        location_ids = self.cleaned_data['assigned_locations']

        if user.is_commcare_user():
            old_location_id = user.location_id
            if location_id != old_location_id:
                if location_id:
                    user.set_location(SQLLocation.objects.get(location_id=location_id))
                else:
                    user.unset_location()

            old_location_ids = user.assigned_location_ids
            if set(location_ids) != set(old_location_ids):
                user.reset_locations(location_ids)
        else:
            domain_membership = user.get_domain_membership(self.domain)
            old_location_id = domain_membership.location_id
            if location_id != old_location_id:
                if location_id:
                    user.set_location(self.domain, SQLLocation.objects.get(location_id=location_id))
                else:
                    user.unset_location(self.domain)

            old_location_ids = domain_membership.assigned_location_ids
            if set(location_ids) != set(old_location_ids):
                user.reset_locations(self.domain, location_ids)

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
                self.add_error('primary_location',
                               _("Primary location can only be one of user's locations"))
        if assigned_location_ids and not primary_location_id:
            self.add_error('primary_location',
                           _("Primary location can't be empty if user has any locations set"))


class DomainRequestForm(forms.Form):
    full_name = forms.CharField(label=ugettext_lazy('Full Name'), required=True,
                                widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.CharField(
        label=ugettext_lazy('Email Address'),
        required=True,
        help_text=ugettext_lazy('You will use this email to log in.'),
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    domain = forms.CharField(widget=forms.HiddenInput(), required=True)

    @property
    def form_actions(self):
        return hqcrispy.FormActions(
            twbscrispy.StrictButton(
                ugettext_lazy('Request Access'),
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
            hqcrispy.Field('full_name'),
            hqcrispy.Field('email'),
            hqcrispy.Field('domain'),
            self.form_actions,
        )

    def clean_email(self):
        data = self.cleaned_data['email'].strip().lower()
        validate_email(data)
        return data


class ConfirmExtraUserChargesForm(EditBillingAccountInfoForm):
    def __init__(self, account, domain, creating_user, data=None, *args, **kwargs):
        super(ConfirmExtraUserChargesForm, self).__init__(account, domain, creating_user, data=data, *args, **kwargs)

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


class SelfRegistrationForm(forms.Form):

    def __init__(self, *args, **kwargs):
        if 'domain' not in kwargs:
            raise Exception('Expected kwargs: domain')
        self.domain = kwargs.pop('domain')
        require_email = kwargs.pop('require_email', False)

        super(SelfRegistrationForm, self).__init__(*args, **kwargs)

        if require_email:
            self.fields['email'].required = True

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-xs-4'
        self.helper.field_class = 'col-xs-8'
        layout_fields = [
            crispy.Fieldset(
                _('Register'),
                crispy.Field('username', placeholder='sam123'),
                crispy.Field('password'),
                crispy.Field('password2'),
                crispy.Field('email'),
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _('Register'),
                    css_class='btn-primary',
                    type='submit',
                )
            ),
        ]
        self.helper.layout = crispy.Layout(*layout_fields)

    username = TrimmedCharField(
        required=True,
        label=ugettext_lazy('Create a Username'),
    )
    password = forms.CharField(
        required=True,
        label=ugettext_lazy('Create a Password'),
        widget=PasswordInput(),
    )
    password2 = forms.CharField(
        required=True,
        label=ugettext_lazy('Re-enter Password'),
        widget=PasswordInput(),
    )
    email = forms.EmailField(
        required=False,
        label=ugettext_lazy('Email address (used for tasks like resetting your password)'),
    )

    def clean_username(self):
        return clean_mobile_worker_username(
            self.domain,
            self.cleaned_data.get('username')
        )

    def clean_password2(self):
        if self.cleaned_data.get('password') != self.cleaned_data.get('password2'):
            raise forms.ValidationError(_('Passwords do not match.'))


class AddPhoneNumberForm(forms.Form):
    phone_number = forms.CharField(
        max_length=50, help_text=ugettext_lazy('Please enter number, including country code, in digits only.')
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
        self.fields['phone_number'].label = ugettext_lazy('Phone number')


class CommCareUserFormSet(object):
    """Combines the CommCareUser form and the Custom Data form"""

    def __init__(self, domain, editable_user, request_user, data=None, *args, **kwargs):
        self.domain = domain
        self.editable_user = editable_user
        self.request_user = request_user
        self.data = data

    @property
    @memoized
    def user_form(self):
        return UpdateCommCareUserInfoForm(
            data=self.data, domain=self.domain, existing_user=self.editable_user)

    @property
    @memoized
    def custom_data(self):
        from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
        return CustomDataEditor(
            domain=self.domain,
            field_view=UserFieldsView,
            existing_custom_data=self.editable_user.user_data,
            post_dict=self.data,
        )

    def is_valid(self):
        return (self.data is not None
                and all([self.user_form.is_valid(), self.custom_data.is_valid()]))

    def update_user(self):
        self.user_form.existing_user.user_data = self.custom_data.get_data_to_save()
        return self.user_form.update_user()


class CommCareUserFilterForm(forms.Form):
    USERNAMES_COLUMN_OPTION = 'usernames'
    COLUMNS_CHOICES = (
        ('all', ugettext_noop('All')),
        (USERNAMES_COLUMN_OPTION, ugettext_noop('Only Usernames'))
    )
    role_id = forms.ChoiceField(label=ugettext_lazy('Role'), choices=(), required=False)
    search_string = forms.CharField(
        label=ugettext_lazy('Search by username'),
        max_length=30,
        required=False
    )
    location_id = forms.CharField(
        label=ugettext_noop("Location"),
        required=False,
    )
    columns = forms.ChoiceField(
        required=False,
        label=ugettext_noop("Columns"),
        choices=COLUMNS_CHOICES,
        widget=SelectToggle(choices=COLUMNS_CHOICES, apply_bindings=True),
    )

    def __init__(self, *args, **kwargs):
        from corehq.apps.locations.forms import LocationSelectWidget
        self.domain = kwargs.pop('domain')
        super(CommCareUserFilterForm, self).__init__(*args, **kwargs)
        self.fields['location_id'].widget = LocationSelectWidget(self.domain)
        self.fields['location_id'].help_text = ExpandedMobileWorkerFilter.location_search_help

        roles = UserRole.by_domain(self.domain)
        self.fields['role_id'].choices = [('', _('All Roles'))] + [
            (role._id, role.name or _('(No Name)')) for role in roles]

        self.helper = FormHelper()
        self.helper.form_method = 'GET'
        self.helper.form_id = 'user-filters'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_action = reverse('download_commcare_users', args=[self.domain])

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_text_inline = True

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Filter and Download Users"),
                crispy.Field('role_id', css_class="hqwebapp-select2"),
                crispy.Field('search_string'),
                crispy.Field('location_id'),
                crispy.Field('columns'),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Download All Users"),
                    type="submit",
                    css_class="btn btn-primary submit_button",
                )
            ),
        )

    def clean_role_id(self):
        role_id = self.cleaned_data['role_id']
        if not role_id:
            return None
        if not UserRole.get(role_id).domain == self.domain:
            raise forms.ValidationError(_("Invalid Role"))
        return role_id

    def clean_search_string(self):
        search_string = self.cleaned_data['search_string']
        if "*" in search_string or "?" in search_string:
            raise forms.ValidationError(_("* and ? are not allowed"))
        return search_string
