from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
from django.contrib.auth.forms import SetPasswordForm
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms.layout import Div, Fieldset, HTML, Layout, Submit
import datetime

from corehq.apps.hqwebapp.widgets import Select2Ajax
from dimagi.utils.django.fields import TrimmedCharField
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, validate_email
from django.urls import reverse
from django.forms.widgets import PasswordInput
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext_noop, string_concat
from django.template.loader import get_template
from django_countries.data import COUNTRIES

from corehq import toggles
from corehq.apps.analytics.tasks import set_analytics_opt_out
from corehq.apps.custom_data_fields import CustomDataEditor
from corehq.apps.domain.forms import EditBillingAccountInfoForm, clean_password
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import user_can_access_location_id
from custom.nic_compliance.forms import EncodedPasswordChangeFormMixin
from corehq.apps.users.models import CouchUser, UserRole
from corehq.apps.users.const import ANONYMOUS_USERNAME
from corehq.apps.users.util import format_username, cc_user_domain
from corehq.apps.app_manager.models import validate_lang
from corehq.apps.programs.models import Program
from corehq.apps.hqwebapp.utils import decode_password
# Bootstrap 3 Crispy Forms
from crispy_forms import layout as cb3_layout
from crispy_forms import helper as cb3_helper
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.hqwebapp import crispy as hqcrispy

from corehq.util.soft_assert import soft_assert
from memoized import memoized

import re

# required to translate inside of a mark_safe tag
from django.utils.functional import lazy
import six  # Python 3 compatibility
from six.moves import range
mark_safe_lazy = lazy(mark_safe, six.text_type)

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
    email_opt_out = forms.BooleanField(
        required=False,
        label=ugettext_lazy("Opt out of emails about CommCare updates."),
    )
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

        self.new_helper = cb3_helper.FormHelper()
        self.new_helper.form_method = 'POST'
        self.new_helper.form_class = 'form-horizontal'
        self.new_helper.attrs = {
            'name': 'user_information',
        }
        self.new_helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.new_helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        basic_fields = [
            cb3_layout.Div(*username_controls),
            hqcrispy.Field('first_name'),
            hqcrispy.Field('last_name'),
            hqcrispy.Field('email'),
        ]
        if self.set_analytics_enabled:
            basic_fields.append(twbscrispy.PrependedText('analytics_enabled', ''),)
        if self.set_email_opt_out:
            basic_fields.append(twbscrispy.PrependedText('email_opt_out', ''))

        self.new_helper.layout = cb3_layout.Layout(
            cb3_layout.Fieldset(
                ugettext_lazy("Basic"),
                *basic_fields
            ),
            (hqcrispy.FieldsetAccordionGroup if self.collapse_other_options else cb3_layout.Fieldset)(
                ugettext_lazy("Other Options"),
                hqcrispy.Field('language'),
                cb3_layout.Div(*api_key_controls),
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
    def set_email_opt_out(self):
        return self.user.is_web_user() and not settings.ENTERPRISE_MODE

    @property
    def collapse_other_options(self):
        return self.user.is_commcare_user()

    @property
    def direct_properties(self):
        result = list(self.fields)
        if not self.set_analytics_enabled:
            result.remove('analytics_enabled')
        if not self.set_email_opt_out:
            result.remove('email_opt_out')
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
            self.fields['new_password1'].help_text = mark_safe_lazy(string_concat('<i class="fa fa-warning"></i>',
                 ugettext_lazy("This password is automatically generated. Please copy it or create your own. It will not be shown again."),
                 '<br /><span data-bind="text: passwordHelp, css: color">'
            ))
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
    password = forms.CharField(widget=PasswordInput(), required=True, min_length=1)
    password_2 = forms.CharField(label='Password (reenter)', widget=PasswordInput(), required=True, min_length=1)
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
                'password',
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
        phone_number = re.sub('\s|\+|\-', '', phone_number)
        if phone_number == '':
            return None
        elif not re.match(r'\d+$', phone_number):
            raise forms.ValidationError(_("%s is an invalid phone number." % phone_number))
        return phone_number

    def clean(self):
        try:
            password = self.cleaned_data['password']
            password_2 = self.cleaned_data['password_2']
        except KeyError:
            pass
        else:
            if password != password_2:
                raise forms.ValidationError("Passwords do not match")

        return self.cleaned_data

validate_username = EmailValidator(message=ugettext_lazy('Username contains invalid characters.'))


_username_help = """
<span ng-if="usernameAvailabilityStatus === 'pending'">
    <i class="fa fa-circle-o-notch fa-spin"></i>
    %(checking)s
</span>
<span ng-if="usernameAvailabilityStatus === 'taken'"
      style="word-wrap:break-word;">
    <i class="fa fa-remove"></i>
    {{ usernameStatusMessage }}
</span>
<span ng-if="usernameAvailabilityStatus === 'available'"
      style="word-wrap:break-word;">
    <i class="fa fa-check"></i>
    {{ usernameStatusMessage }}
</span>
<span ng-if="usernameAvailabilityStatus === 'warning'">
    <i class="fa fa-exclamation-triangle"></i>
    {{ usernameStatusMessage }}
</span>
<span ng-if="usernameAvailabilityStatus === 'error'">
    <i class="fa fa-exclamation-triangle"></i>
    %(server_error)s
</span>
""" % {
    'checking': ugettext_noop('Checking Availability...'),
    'server_error': ugettext_noop('Issue connecting to server. Check Internet connection.')
}


class NewMobileWorkerForm(forms.Form):
    username = forms.CharField(
        max_length=50,
        required=True,
        help_text=_username_help,
        label=ugettext_noop("Username"),
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        label=ugettext_noop("First Name")
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
    password = forms.CharField(
        widget=forms.PasswordInput(),
        required=True,
        min_length=1,
        label=ugettext_noop("Password"),
    )

    def __init__(self, project, request_user, *args, **kwargs):
        super(NewMobileWorkerForm, self).__init__(*args, **kwargs)
        email_string = "@{}.commcarehq.org".format(project.name)
        max_chars_username = 80 - len(email_string)
        self.project = project
        self.domain = self.project.name
        self.request_user = request_user
        self.can_access_all_locations = request_user.has_permission(self.domain, 'access_all_locations')
        if not self.can_access_all_locations:
            self.fields['location_id'].required = True

        if self.project.strong_mobile_passwords:
            if settings.ENABLE_DRACONIAN_SECURITY_FEATURES:
                validator = "validate_password_draconian"
            else:
                validator = "validate_password_standard"
            self.fields['password'].widget = forms.TextInput(attrs={
                validator: "",
                "ng_keydown": "markNonDefault()",
                "class": "default",
            })
            self.fields['password'].help_text = mark_safe_lazy(string_concat('<i class="fa fa-warning"></i>',
                ugettext_lazy('This password is automatically generated. Please copy it or create your own. It will not be shown again.'),
                '<br />'
            ))

        if project.uses_locations:
            self.fields['location_id'].widget = AngularLocationSelectWidget(
                require=not self.can_access_all_locations)
            location_field = crispy.Field(
                'location_id',
                ng_model='mobileWorker.location_id',
            )
        else:
            location_field = crispy.Hidden(
                'location_id',
                '',
                ng_model='mobileWorker.location_id',
            )

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-4'
        self.helper.field_class = 'col-sm-8'
        self.helper.layout = Layout(
            Fieldset(
                _('Basic Information'),
                crispy.Field(
                    'username',
                    ng_required="true",
                    validate_username="",
                    # What this says is, update as normal or when the element
                    # loses focus. If the update is normal, wait 300 ms to
                    # send the request again. If the update is on blur,
                    # send the request.
                    ng_model_options="{ "
                                      " updateOn: 'default blur', "
                                      " debounce: {'default': 300, 'blur': 0} "
                                      "}",
                    ng_model='mobileWorker.username',
                    ng_maxlength=max_chars_username,
                    maxlength=max_chars_username,
                ),
                crispy.Field(
                    'first_name',
                    ng_required="false",
                    ng_model='mobileWorker.first_name',
                    ng_maxlength="30",
                ),
                crispy.Field(
                    'last_name',
                    ng_required="false",
                    ng_model='mobileWorker.last_name',
                    ng_maxlength="30",
                ),
                location_field,
                crispy.Field(
                    'password',
                    ng_required="true",
                    ng_model='mobileWorker.password',
                    data_bind="value: password, valueUpdate: 'input'",
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

    def clean_password(self):
        cleaned_password = decode_password(self.cleaned_data.get('password'))
        if self.project.strong_mobile_passwords:
            return clean_password(cleaned_password)
        return cleaned_password


class NewAnonymousMobileWorkerForm(forms.Form):
    location_id = forms.CharField(
        label=ugettext_noop("Location"),
        required=False,
    )
    username = forms.CharField(
        max_length=50,
        label=ugettext_noop("Username"),
        initial=ANONYMOUS_USERNAME,
    )
    password = forms.CharField(
        required=True,
        min_length=1,
    )

    def __init__(self, project, request_user, *args, **kwargs):
        super(NewAnonymousMobileWorkerForm, self).__init__(*args, **kwargs)
        self.project = project
        self.request_user = request_user
        self.can_access_all_locations = request_user.has_permission(self.project.name, 'access_all_locations')
        if not self.can_access_all_locations:
            self.fields['location_id'].required = True

        if project.uses_locations:
            self.fields['location_id'].widget = AngularLocationSelectWidget(
                require=not self.can_access_all_locations)
            location_field = crispy.Field(
                'location_id',
                ng_model='mobileWorker.location_id',
            )
        else:
            location_field = crispy.Hidden(
                'location_id',
                '',
                ng_model='mobileWorker.location_id',
            )

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-4'
        self.helper.field_class = 'col-sm-8'
        self.helper.layout = Layout(
            Fieldset(
                _('Basic Information'),
                crispy.Field(
                    'username',
                    readonly=True,
                ),
                location_field,
                crispy.Hidden('is_anonymous', 'yes'),
            )
        )


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

        # html
        <script>
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
        </script>
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


class AngularLocationSelectWidget(forms.Widget):
    """
    Assumptions:
        mobileWorker.location_id is model
        scope has searchLocations function to search
        scope uses availableLocations to search in
    """

    def __init__(self, require=False, attrs=None):
        self.require = require
        super(AngularLocationSelectWidget, self).__init__(attrs)

    def render(self, name, value, attrs=None):
        # The .format() means I have to use 4 braces to end up with {{$select.selected.name}}
        return """
          <ui-select {validator} ng-model="mobileWorker.location_id" theme="select2" style="width: 300px;">
            <ui-select-match placeholder="Select location...">{{{{$select.selected.name}}}}</ui-select-match>
            <ui-select-choices refresh="searchLocations($select.search)" refresh-delay="0" repeat="location.id as location in availableLocations | filter:$select.search">
              <div ng-bind-html="location.name | highlight: $select.search"></div>
            </ui-select-choices>
          </ui-select>
        """.format(validator='validate-location=""' if self.require else '')


class SupplyPointSelectWidget(forms.Widget):

    def __init__(self, domain, attrs=None, id='supply-point', multiselect=False, query_url=None):
        super(SupplyPointSelectWidget, self).__init__(attrs)
        self.domain = domain
        self.id = id
        self.multiselect = multiselect
        if query_url:
            self.query_url = query_url
        else:
            self.query_url = reverse('child_locations_for_select2', args=[self.domain])

    def render(self, name, value, attrs=None):
        location_ids = value.split(',') if value else []
        locations = list(SQLLocation.active_objects
                         .filter(domain=self.domain, location_id__in=location_ids))
        initial_data = [{'id': loc.location_id, 'name': loc.get_path_display()} for loc in locations]

        return get_template('locations/manage/partials/autocomplete_select_widget.html').render({
            'id': self.id,
            'name': name,
            'value': ','.join(loc.location_id for loc in locations),
            'query_url': self.query_url,
            'multiselect': self.multiselect,
            'initial_data': initial_data,
        })


class PrimaryLocationWidget(forms.Widget):
    """
    Options for this field are dynamically set in JS depending on what options are selected
    for 'assigned_locations'. This works in conjunction with SupplyPointSelectWidget.
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

    def render(self, name, value, attrs=None):
        return get_template('locations/manage/partials/drilldown_location_widget.html').render({
            'css_id': self.css_id,
            'source_css_id': self.source_css_id,
            'name': name,
            'value': value or ''
        })


class CommtrackUserForm(forms.Form):
    assigned_locations = forms.CharField(
        label=ugettext_noop("Locations"),
        required=False,
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
        self.domain = None
        if 'domain' in kwargs:
            self.domain = kwargs['domain']
            del kwargs['domain']
        super(CommtrackUserForm, self).__init__(*args, **kwargs)
        self.fields['assigned_locations'].widget = SupplyPointSelectWidget(
            self.domain, multiselect=True, id='id_assigned_locations'
        )
        self.fields['primary_location'].widget = PrimaryLocationWidget(
            css_id='id_primary_location',
            source_css_id='id_assigned_locations'
        )
        if self.commtrack_enabled:
            programs = Program.by_domain(self.domain, wrap=False)
            choices = list((prog['_id'], prog['name']) for prog in programs)
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
        # select2 (< 4.0) doesn't format multiselect for remote data as an array
        #   but formats it as comma-seperated list, so we need to clean the returned data
        from corehq.apps.locations.models import SQLLocation
        from corehq.apps.locations.util import get_locations_from_ids

        value = self.cleaned_data.get('assigned_locations')
        if not isinstance(value, six.string_types) or value.strip() == '':
            return []

        location_ids = [location_id.strip() for location_id in value.split(',')]
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

        self.helper = cb3_helper.FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-6 col-md-5 col-lg-3'
        self.helper.show_form_errors = True
        self.helper.layout = cb3_layout.Layout(
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
                crispy.Field('email_list', css_class='input-xxlarge accounting-email-select2'),
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
                             data_countryname=COUNTRIES.get(self.current_country, '')),
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
                twbscrispy.PrependedText('phone_number', '+', type='tel', pattern='\d+')
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
    role_id = forms.ChoiceField(label=ugettext_lazy('Role'), choices=(), required=False)
    search_string = forms.CharField(
        label=ugettext_lazy('Search by username'),
        max_length=30,
        required=False
    )

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain')
        super(CommCareUserFilterForm, self).__init__(*args, **kwargs)

        roles = UserRole.by_domain(self.domain)
        self.fields['role_id'].choices =  [('', _('All Roles'))] + [
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
                crispy.Field('role_id'),
                crispy.Field('search_string'),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Download All Users"),
                    type="submit",
                    css_class="btn btn-success submit_button",
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
