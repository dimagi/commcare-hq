from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Div, Fieldset, HTML, Layout, Submit
from django import forms
from django.core.validators import EmailValidator, email_re
from django.core.urlresolvers import reverse
from django.forms.widgets import PasswordInput, HiddenInput
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from django.template.loader import get_template
from django.template import Context
from corehq.apps.locations.models import Location
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import format_username
from corehq.apps.app_manager.models import validate_lang
from corehq.apps.commtrack.models import CommTrackUser
import re


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
        'invalid': _(u'Please enter a valid two or three digit language code.'),
    }
    default_validators = [wrapped_language_validation]


class BaseUpdateUserForm(forms.Form):

    @property
    def direct_properties(self):
        return []

    def update_user(self, existing_user=None, **kwargs):
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

        if is_update_successful:
            existing_user.save()
        return is_update_successful

    def initialize_form(self, existing_user=None, **kwargs):
        if existing_user is None:
            return

        for prop in self.direct_properties:
            self.initial[prop] = getattr(existing_user, prop, "")


class UpdateUserRoleForm(BaseUpdateUserForm):
    role = forms.ChoiceField(choices=(), required=False)

    def update_user(self, existing_user=None, domain=None, **kwargs):
        is_update_successful = super(UpdateUserRoleForm, self).update_user(existing_user)

        if domain and 'role' in self.cleaned_data:
            role = self.cleaned_data['role']
            try:
                existing_user.set_role(domain, role)
                existing_user.save()
                is_update_successful = True
            except KeyError:
                pass

        return is_update_successful

    def load_roles(self, role_choices=None, current_role=None):
        if role_choices is None:
            role_choices = []
        self.fields['role'].choices = role_choices

        if current_role:
            self.initial['role'] = current_role


class BaseUserInfoForm(forms.Form):
    first_name = forms.CharField(label=ugettext_lazy('First Name'), max_length=50, required=False)
    last_name = forms.CharField(label=ugettext_lazy('Last Name'), max_length=50, required=False)
    email = forms.EmailField(label=ugettext_lazy("E-mail"), max_length=75, required=False)
    language = forms.ChoiceField(choices=(), initial=None, required=False, help_text=mark_safe(ugettext_lazy(
        "<i class=\"icon-info-sign\"></i> Becomes default language seen in CloudCare and reports (if applicable). "
        "Supported languages for reports are en, fr (partial), and hin (partial)."
    )))

    def load_language(self, language_choices=None):
        if language_choices is None:
            language_choices = []
        self.fields['language'].choices = [('', '')] + language_choices


class UpdateMyAccountInfoForm(BaseUpdateUserForm, BaseUserInfoForm):
    email_opt_out = forms.BooleanField(
        required=False,
        label="",
        help_text=ugettext_lazy("Opt out of emails about new features and other CommCare updates.")
    )

    @property
    def direct_properties(self):
        return self.fields.keys()


class UpdateCommCareUserInfoForm(BaseUserInfoForm, UpdateUserRoleForm):

    @property
    def direct_properties(self):
        indirect_props = ['role']
        return [k for k in self.fields.keys() if k not in indirect_props]


class RoleForm(forms.Form):

    def __init__(self, *args, **kwargs):
        if kwargs.has_key('role_choices'):
            role_choices = kwargs.pop('role_choices')
        else:
            role_choices = ()
        super(RoleForm, self).__init__(*args, **kwargs)
        self.fields['role'].choices = role_choices


class Meta:
        app_label = 'users'


class CommCareAccountForm(forms.Form):
    """
    Form for CommCareAccounts
    """
    # 128 is max length in DB
    # 25 is domain max length
    # @{domain}.commcarehq.org adds 16
    # left over is 87 and 80 just sounds better
    max_len_username = 80

    username = forms.CharField(max_length=max_len_username, required=True)
    password = forms.CharField(widget=PasswordInput(), required=True, min_length=1, help_text="Only numbers are allowed in passwords")
    password_2 = forms.CharField(label='Password (reenter)', widget=PasswordInput(), required=True, min_length=1)
    domain = forms.CharField(widget=HiddenInput())
    phone_number = forms.CharField(max_length=80, required=False)

    class Meta:
        app_label = 'users'

    def __init__(self, *args, **kwargs):
        super(forms.Form, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Create new Mobile Worker account',
                'username',
                'password',
                HTML("{% if only_numeric %}"
                     "<div class=\"control-group\"><div class=\"controls\">"
                     "To enable alphanumeric passwords, go to the "
                     "applications this user will use, go to CommCare "
                     "Settings, and change Password Format to Alphanumeric."
                     "</div></div>"
                     "{% endif %}"
                ),
                'password_2',
                'phone_number',
                Div(
                    Div(HTML("Please enter number, including international code, in digits only."),
                        css_class="controls"),
                    css_class="control-group"
                )
            ),
            FormActions(
                ButtonHolder(
                    Submit('submit', 'Create Mobile Worker')
                )
            )
        )

    def clean_phone_number(self):
        phone_number = self.cleaned_data['phone_number']
        phone_number = re.sub('\s|\+|\-', '', phone_number)
        if phone_number == '':
            return None
        elif not re.match(r'\d+$', phone_number):
            raise forms.ValidationError(_("%s is an invalid phone number." % phone_number))
        return phone_number

    def clean_username(self):
        username = self.cleaned_data['username']
        if username == 'admin' or username == 'demo_user':
            raise forms.ValidationError("The username %s is reserved for CommCare." % username)
        return username

    def clean(self):
        try:
            password = self.cleaned_data['password']
            password_2 = self.cleaned_data['password_2']
        except KeyError:
            pass
        else:
            if password != password_2:
                raise forms.ValidationError("Passwords do not match")
            if self.password_format == 'n' and not password.isnumeric():
                raise forms.ValidationError("Password is not numeric")

        try:
            username = self.cleaned_data['username']
        except KeyError:
            pass
        else:
            if len(username) > CommCareAccountForm.max_len_username:
                raise forms.ValidationError(
                    "Username %s is too long.  Must be under %d characters."
                    % (username, CommCareAccountForm.max_len_username))
            validate_username('%s@commcarehq.org' % username)
            domain = self.cleaned_data['domain']
            username = format_username(username, domain)
            num_couch_users = len(CouchUser.view("users/by_username",
                                                 key=username))
            if num_couch_users > 0:
                raise forms.ValidationError("CommCare user already exists")

            # set the cleaned username to user@domain.commcarehq.org
            self.cleaned_data['username'] = username
        return self.cleaned_data

validate_username = EmailValidator(email_re, _(u'Username contains invalid characters.'), 'invalid')


class MultipleSelectionForm(forms.Form):
    """
    Form for selecting groups (used by the group UI on the user page)
    """
    selected_ids = forms.MultipleChoiceField(
        label="",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.add_input(Submit('submit', 'Update'))
        super(MultipleSelectionForm, self).__init__(*args, **kwargs)


class SupplyPointSelectWidget(forms.Widget):
    def __init__(self, attrs=None, domain=None, id='supply-point'):
        super(SupplyPointSelectWidget, self).__init__(attrs)
        self.domain = domain
        self.id = id

    def render(self, name, value, attrs=None):
        return get_template('locations/manage/partials/autocomplete_select_widget.html').render(Context({
                    'id': self.id,
                    'name': name,
                    'value': value or '',
                    'query_url': reverse('corehq.apps.commtrack.views.api_query_supply_point', args=[self.domain]),
                }))

class CommtrackUserForm(forms.Form):
    supply_point = forms.CharField(label='Supply Point:', required=False)

    def __init__(self, *args, **kwargs):
        domain = None
        if 'domain' in kwargs:
            domain = kwargs['domain']
            del kwargs['domain']
        super(CommtrackUserForm, self).__init__(*args, **kwargs)
        self.fields['supply_point'].widget = SupplyPointSelectWidget(domain=domain)

    def save(self, user):
        commtrack_user = CommTrackUser.wrap(user.to_json())
        location_id = self.cleaned_data['supply_point']
        if location_id:
            loc = Location.get(location_id)
            commtrack_user.clear_locations()
            commtrack_user.add_location(loc)
