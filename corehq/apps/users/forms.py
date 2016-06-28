from django.contrib.auth.forms import SetPasswordForm
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms.layout import Div, Fieldset, HTML, Layout, Submit
import datetime
from dimagi.utils.django.fields import TrimmedCharField
from django import forms
from django.core.validators import EmailValidator, validate_email
from django.core.urlresolvers import reverse
from django.forms.widgets import PasswordInput
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext_noop
from django.template.loader import get_template
from django.template import Context
from django_countries.data import COUNTRIES

from corehq import toggles
from corehq.apps.domain.forms import EditBillingAccountInfoForm
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import format_username, cc_user_domain
from corehq.apps.app_manager.models import validate_lang
from corehq.apps.programs.models import Program

# Bootstrap 3 Crispy Forms
from crispy_forms import layout as cb3_layout
from crispy_forms import helper as cb3_helper
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.style import crispy as hqcrispy

import re

# required to translate inside of a mark_safe tag
from django.utils.functional import lazy
import six  # Python 3 compatibility
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


class LanguageField(forms.CharField):
    """
    Adds language code validation to a field
    """

    def __init__(self, *args, **kwargs):
        super(LanguageField, self).__init__(*args, **kwargs)
        self.min_length = 2
        self.max_length = 3

    default_error_messages = {
        'invalid': ugettext_lazy(u'Please enter a valid two or three digit language code.'),
    }
    default_validators = [wrapped_language_validation]


class BaseUpdateUserForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(BaseUpdateUserForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

    @property
    def direct_properties(self):
        return []

    def clean_email(self):
        return self.cleaned_data['email'].lower()

    def update_user(self, existing_user=None, save=True, **kwargs):
        is_update_successful = False
        if not existing_user and 'email' in self.cleaned_data:
            from django.contrib.auth.models import User
            django_user = User()
            django_user.username = self.cleaned_data['email']
            django_user.save()
            existing_user = CouchUser.from_django_user(django_user)
            existing_user.save()
            is_update_successful = True

        for prop in self.direct_properties:
            setattr(existing_user, prop, self.cleaned_data[prop])
            is_update_successful = True

        if is_update_successful and save:
            existing_user.save()
        return is_update_successful

    def initialize_form(self, domain, existing_user=None):
        if existing_user is None:
            return

        for prop in self.direct_properties:
            self.initial[prop] = getattr(existing_user, prop, "")


class UpdateUserRoleForm(BaseUpdateUserForm):
    role = forms.ChoiceField(choices=(), required=False)

    def update_user(self, existing_user=None, domain=None, **kwargs):
        is_update_successful = super(UpdateUserRoleForm, self).update_user(existing_user, save=False)

        if domain and 'role' in self.cleaned_data:
            role = self.cleaned_data['role']
            try:
                existing_user.set_role(domain, role)
                existing_user.save()
                is_update_successful = True
            except KeyError:
                pass
        elif is_update_successful:
            existing_user.save()

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
    first_name = forms.CharField(label=ugettext_lazy('First Name'), max_length=50, required=False)
    last_name = forms.CharField(label=ugettext_lazy('Last Name'), max_length=50, required=False)
    email = forms.EmailField(label=ugettext_lazy("E-Mail"), max_length=75, required=False)
    language = forms.ChoiceField(
        choices=(),
        initial=None,
        required=False,
        help_text=mark_safe_lazy(
            ugettext_lazy(
                "<i class=\"fa fa-info-circle\"></i> "
                "Becomes default language seen in CloudCare and reports (if applicable), "
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

    def __init__(self, *args, **kwargs):
        self.username = kwargs.pop('username') if 'username' in kwargs else None
        self.user = kwargs.pop('user') if 'user' in kwargs else None
        api_key = kwargs.pop('api_key') if 'api_key' in kwargs else None

        super(UpdateMyAccountInfoForm, self).__init__(*args, **kwargs)

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
        self.new_helper.layout = cb3_layout.Layout(
            cb3_layout.Fieldset(
                ugettext_lazy("Basic"),
                cb3_layout.Div(*username_controls),
                hqcrispy.Field('first_name'),
                hqcrispy.Field('last_name'),
                hqcrispy.Field('email'),
                twbscrispy.PrependedText('email_opt_out', ''),
            ),
            cb3_layout.Fieldset(
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
    def direct_properties(self):
        return self.fields.keys()


class UpdateCommCareUserInfoForm(BaseUserInfoForm, UpdateUserRoleForm):
    loadtest_factor = forms.IntegerField(
        required=False, min_value=1, max_value=50000,
        help_text=ugettext_lazy(u"Multiply this user's case load by a number for load testing on phones. "
                    u"Leave blank for normal users."),
        widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super(UpdateCommCareUserInfoForm, self).__init__(*args, **kwargs)
        self.fields['role'].help_text = _(mark_safe(
            "<i class=\"fa fa-info-circle\"></i> "
            "Only applies to mobile workers that will be entering data using "
            "<a href='https://help.commcarehq.org/display/commcarepublic/CloudCare+-+Web+Data+Entry'>"
            "CloudCare</a>"
        ))

    @property
    def direct_properties(self):
        indirect_props = ['role']
        return [k for k in self.fields.keys() if k not in indirect_props]

    def initialize_form(self, domain, existing_user=None):
        if toggles.ENABLE_LOADTEST_USERS.enabled(domain):
            self.fields['loadtest_factor'].widget = forms.TextInput()
        super(UpdateCommCareUserInfoForm, self).initialize_form(domain, existing_user)


class RoleForm(forms.Form):

    def __init__(self, *args, **kwargs):
        if kwargs.has_key('role_choices'):
            role_choices = kwargs.pop('role_choices')
        else:
            role_choices = ()
        super(RoleForm, self).__init__(*args, **kwargs)
        self.fields['role'].choices = role_choices


class SetUserPasswordForm(SetPasswordForm):

    def __init__(self, domain, user_id, **kwargs):
        super(SetUserPasswordForm, self).__init__(**kwargs)

        self.helper = FormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_tag = False

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_action = reverse("change_password", args=[domain, user_id])
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Reset Password for Mobile Worker"),
                'new_password1',
                'new_password2',
                hqcrispy.FormActions(
                    crispy.ButtonHolder(
                        Submit('submit', _('Reset Password'))
                    )
                ),
            ),
        )


class CommCareAccountForm(forms.Form):
    """
    Form for CommCareAccounts
    """
    username = forms.CharField(required=True)
    password = forms.CharField(widget=PasswordInput(), required=True, min_length=1)
    password_2 = forms.CharField(label='Password (reenter)', widget=PasswordInput(), required=True, min_length=1)
    phone_number = forms.CharField(max_length=80, required=False)

    def __init__(self, *args, **kwargs):
        if 'domain' not in kwargs:
            raise Exception('Expected kwargs: domain')
        self.domain = kwargs.pop('domain', None)
        super(forms.Form, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                'Create new Mobile Worker account',
                'username',
                'password',
                'password_2',
                'phone_number',
                Div(
                    Div(HTML("Please enter number, including international code, in digits only."),
                        css_class="controls"),
                    css_class="control-group"
                )
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

validate_username = EmailValidator(message=ugettext_lazy(u'Username contains invalid characters.'))


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
        max_length=50,
        required=False,
        label=ugettext_noop("First Name")
    )
    last_name = forms.CharField(
        max_length=50,
        required=False,
        label=ugettext_noop("Last Name")
    )
    password = forms.CharField(
        widget=PasswordInput(),
        required=True,
        min_length=1,
        label=ugettext_noop("Password")
    )

    def __init__(self, domain, *args, **kwargs):
        super(NewMobileWorkerForm, self).__init__(*args, **kwargs)
        email_string = u"@{}.commcarehq.org".format(domain)
        max_chars_username = 80 - len(email_string)

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
                    ng_maxlength="50",
                ),
                crispy.Field(
                    'last_name',
                    ng_required="false",
                    ng_model='mobileWorker.last_name',
                    ng_maxlength="50",
                ),
                crispy.Field(
                    'password',
                    ng_required="true",
                    ng_model='mobileWorker.password'
                ),
            )
        )

    def clean_username(self):
        username = self.cleaned_data['username']
        if username == 'admin' or username == 'demo_user':
            raise forms.ValidationError("The username %s is reserved for CommCare." % username)
        return username


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
        <script type="text/javascript">
            // Multiselect widget
            $(function () {
                var multiselect_utils = hqImport('style/js/components/multiselect_utils');
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


class SupplyPointSelectWidget(forms.Widget):

    def __init__(self, attrs=None, domain=None, id='supply-point', multiselect=False):
        super(SupplyPointSelectWidget, self).__init__(attrs)
        self.domain = domain
        self.id = id
        self.multiselect = multiselect

    def render(self, name, value, attrs=None):
        return get_template('locations/manage/partials/autocomplete_select_widget.html').render(Context({
            'id': self.id,
            'name': name,
            'value': value or '',
            'query_url': reverse('corehq.apps.locations.views.child_locations_for_select2', args=[self.domain]),
            'multiselect': self.multiselect,
        }))


class CommtrackUserForm(forms.Form):
    location = forms.CharField(label='Location:', required=False)
    program_id = forms.ChoiceField(label="Program", choices=(), required=False)

    def __init__(self, *args, **kwargs):
        domain = None
        if 'domain' in kwargs:
            domain = kwargs['domain']
            del kwargs['domain']
        super(CommtrackUserForm, self).__init__(*args, **kwargs)
        self.fields['location'].widget = SupplyPointSelectWidget(domain=domain)
        if Domain.get_by_name(domain).commtrack_enabled:
            programs = Program.by_domain(domain, wrap=False)
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

    def save(self, user):
        location_id = self.cleaned_data['location']
        # This means it will clear the location associations set in a domain
        # with multiple locations configured. It is acceptable for now because
        # multi location config is a not really supported special flag for IPM.
        if location_id:
            if location_id != user.location_id:
                user.set_location(Location.get(location_id))
        else:
            user.unset_location()


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
    confirm_product_agreement = forms.BooleanField(
        required=True,
    )

    def __init__(self, account, domain, creating_user, data=None, *args, **kwargs):
        super(ConfirmExtraUserChargesForm, self).__init__(account, domain, creating_user, data=data, *args, **kwargs)
        self.fields['confirm_product_agreement'].label = _(
            'I have read and agree to the <a href="%(pa_url)s" target="_blank">'
            'Software Product Subscription Agreement</a>.'
        ) % {'pa_url': reverse('product_agreement')}

        from corehq.apps.users.views.mobile import MobileWorkerListView
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Basic Information"),
                'company_name',
                'first_name',
                'last_name',
                crispy.Field('email_list', css_class='input-xxlarge'),
                'phone_number',
            ),
            crispy.Fieldset(
                 _("Mailing Address"),
                'first_line',
                'second_line',
                'city',
                'state_province_region',
                'postal_code',
                crispy.Field('country', css_class="input-large",
                             data_countryname=COUNTRIES.get(self.current_country, '')),
            ),
            hqcrispy.B3MultiField(
                '',
                crispy.Field('confirm_product_agreement'),
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
                    disabled="disabled",
                    css_id="submit-button-pa",
                ),
                crispy.HTML(
                    '<p class="help-inline" id="submit-button-help-qa" style="vertical-align: '
                    'top; margin-top: 5px; margin-bottom: 0px;">%s</p>' % _("Please agree to the Product Subscription "
                                                                            "Agreement above before continuing.")
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

        super(SelfRegistrationForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-xs-4'
        self.helper.field_class = 'col-xs-8'
        layout_fields = [
            crispy.Fieldset(
                _('Register'),
                crispy.Field('username'),
                crispy.Field('password'),
                crispy.Field('password2'),
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
        label=ugettext_lazy('Username (create a username)'),
    )
    password = forms.CharField(
        required=True,
        label=ugettext_lazy('Password (create a password)'),
        widget=PasswordInput(),
    )
    password2 = forms.CharField(
        required=True,
        label=ugettext_lazy('Re-enter Password'),
        widget=PasswordInput(),
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
