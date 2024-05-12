import json

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.signals import user_login_failed
from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from captcha.fields import ReCaptchaField
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField, StrictButton
from crispy_forms.helper import FormHelper
from memoized import memoized
from two_factor.forms import AuthenticationTokenForm, BackupTokenForm

from corehq.apps.domain.forms import NoAutocompleteMixin
from corehq.apps.users.models import CouchUser
from corehq.util.metrics import metrics_counter

LOCKOUT_MESSAGE = mark_safe(_(  # nosec: no user input
    'Sorry - you have attempted to login with an incorrect password too many times. '
    'Please <a href="/accounts/password_reset_email/">click here</a> to reset your password '
    'or contact the domain administrator.'))


class EmailAuthenticationForm(NoAutocompleteMixin, AuthenticationForm):
    username = forms.EmailField(label=_("Email Address"),
                                widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    if settings.ADD_CAPTCHA_FIELD_TO_FORMS:
        captcha = ReCaptchaField(label="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if settings.ENFORCE_SSO_LOGIN:
            self.fields['username'].widget = forms.TextInput(attrs={
                'class': 'form-control',
                'data-bind': 'textInput: authUsername, onEnterKey: continueOnEnter',
                'placeholder': _("Enter email address"),
            })
            self.fields['password'].widget = forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': _("Enter password"),
            })

    def clean_username(self):
        username = self.cleaned_data.get('username', '').lower()
        return username

    def clean(self):
        username = self.cleaned_data.get('username')
        if username is None:
            raise ValidationError(_('Please enter a valid email address.'))

        password = self.cleaned_data.get('password')
        if not password:
            raise ValidationError(_("Please enter a password."))

        if settings.ADD_CAPTCHA_FIELD_TO_FORMS:
            if not self.cleaned_data.get('captcha'):
                raise ValidationError(_("Please enter valid CAPTCHA"))

        try:
            cleaned_data = super(EmailAuthenticationForm, self).clean()
        except ValidationError:
            user = CouchUser.get_by_username(username)
            if user and user.is_locked_out():
                metrics_counter('commcare.auth.lockouts')
                raise ValidationError(LOCKOUT_MESSAGE)
            else:
                raise
        user = CouchUser.get_by_username(username)
        if user and user.is_locked_out():
            metrics_counter('commcare.auth.lockouts')
            raise ValidationError(LOCKOUT_MESSAGE)
        return cleaned_data


class CloudCareAuthenticationForm(EmailAuthenticationForm):
    username = forms.CharField(label=_("Username"),
                               widget=forms.TextInput(attrs={'class': 'form-control'}))


class BulkUploadForm(forms.Form):
    bulk_upload_file = forms.FileField(label="")
    action = forms.CharField(widget=forms.HiddenInput(), initial='bulk_upload')

    def __init__(self, plural_noun="", action=None, form_id=None, context=None, *args, **kwargs):
        super(BulkUploadForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        if form_id:
            self.helper.form_id = form_id
        self.helper.form_method = 'post'
        if action:
            self.helper.form_action = action
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                "",
                *self.crispy_form_fields(context)
            ),
            StrictButton(
                ('<i class="fa-solid fa-cloud-arrow-up"></i> Upload %s' % plural_noun),
                css_class='btn-primary disable-on-submit',
                data_bind='disable: !file()',
                type='submit',
            ),
        )

    def crispy_form_fields(self, context):
        return [
            crispy.Field(
                'bulk_upload_file',
                data_bind="value: file",
            ),
            crispy.Field(
                'action',
            ),
        ]


class AppTranslationsBulkUploadForm(BulkUploadForm):
    language = forms.CharField(widget=forms.HiddenInput)
    validate = forms.BooleanField(label="Just validate and not update translations", required=False,
                                  initial=False)

    def crispy_form_fields(self, context):
        crispy_form_fields = super(AppTranslationsBulkUploadForm, self).crispy_form_fields(context)
        if context.get('can_select_language'):
            crispy_form_fields.extend([
                InlineField('language', data_bind="value: lang")
            ])
        if context.get('can_validate_app_translations'):
            crispy_form_fields.extend([
                crispy.Div(InlineField('validate'))
            ])
        return crispy_form_fields


class FormListForm(object):
    """
    A higher-level form for editing an arbitrary number of instances of one
    sub-form in a tabular fashion.

    child_form_class: Normal django form used to handle individual rows
    columns: Spec listing columns to appear in the report.
        For normal django fields, just specify the corresponding attribute
        To display arbitrary data, specify a {'label': ..., 'key': ...} dict.

    API:
        is_valid
        cleaned_data
        errors
        as_table

    Example:

    class SingleUserFavorites(forms.Form):
        favorite_color = forms.CharField()
        favorite_food = forms.CharField()

        def clean_favorite_food(self):
            food = self.cleaned_data['favorite_food']
            if food.lower() == "brussels sprouts":
                raise forms.ValidationError("No one likes {}!".format(food))
            return food

    class UserFavoritesForm(FormListForm):
        child_form_class = SingleUserFavorites
        columns = [
            {'label': "Username", 'key': 'username'},
            'favorite_food',
            'favorite_color',
        ]

    class UserFavoritesView(TemplateView):
        @property
        @memoized
        def user_favorites_form(self):
            if self.request.method == "POST":
                data = self.request.POST
            else:
                data = [{
                    'username': user.username,
                    'favorite_food': user.food,
                    'favorite_color': user.color,
                } for user in self.users]
            return UserFavoritesForm(data)
    """
    child_form_class = None  # Django form which controls each row
    # child_form_template = None
    # TODO Use child_form_class `slug` field to enforce uniqueness
    # sortable = False
    # deletable = False
    # can_add_elements = False
    columns = None  # list configuring the columns to display

    child_form_data = forms.CharField(widget=forms.HiddenInput)
    template = "hqwebapp/partials/bootstrap3/form_list_form.html"

    def __init__(self, data=None, request=None, *args, **kwargs):
        self.request = request

        if self.child_form_class is None:
            raise NotImplementedError("You must specify a child form to use"
                                      "for each row")
        if self.columns is None:
            raise NotImplementedError("You must specify columns for your table")
        self.data = data

    @property
    @memoized
    def child_forms(self):
        if isinstance(self.data, QueryDict):
            try:
                rows = json.loads(self.data.get('child_form_data', ""))
            except ValueError as e:
                raise ValidationError("POST request poorly formatted. {}"
                                      .format(str(e)))
        else:
            rows = self.data
        return [
            self.child_form_class(row)
            for row in rows
        ]

    def clean_child_forms(self):
        """
        Populates self.errors and self.cleaned_data
        """
        self.errors = False
        self.cleaned_data = []
        for child_form in self.child_forms:
            child_form.is_valid()
            self.cleaned_data.append(self.form_to_json(child_form))
            if child_form.errors:
                self.errors = True

    def is_valid(self):
        if not hasattr(self, 'errors'):
            self.clean_child_forms()
        return not self.errors

    def get_child_form_field(self, key):
        return self.child_form_class.base_fields.get(key, None)

    def get_header_json(self):
        columns = []
        for header in self.columns:
            if isinstance(header, dict):
                columns.append(header['label'])
            elif isinstance(self.get_child_form_field(header), forms.Field):
                columns.append(self.get_child_form_field(header).label)
            else:
                raise NotImplementedError("Sorry, I don't recognize the "
                                          "column {}".format(header))
        return columns

    def get_row_spec(self):
        columns = []
        for header in self.columns:
            if isinstance(header, dict):
                columns.append({'type': 'RAW',
                                'key': header['key']})
            elif isinstance(self.get_child_form_field(header), forms.Field):
                field = self.get_child_form_field(header)
                html_attrs = field.widget.attrs
                html_attrs['type'] = field.widget.input_type
                columns.append({'type': field.widget.__class__.__name__,
                                'html_attrs': html_attrs,
                                'key': header})
        return columns

    def form_to_json(self, form):
        """
        Converts a child form to JSON for rendering
        """
        cleaned_data = getattr(form, 'cleaned_data', {})

        def get_data(key):
            if key in cleaned_data:
                return cleaned_data[key]
            return form.data.get(key)

        json_row = {}
        for header in self.columns:
            if isinstance(header, dict):
                json_row[header['key']] = get_data(header['key'])
            elif isinstance(self.get_child_form_field(header), forms.Field):
                json_row[header] = get_data(header)
        if getattr(form, 'errors', None):
            json_row['form_errors'] = form.errors
        return json_row

    def get_context(self):
        return {
            'headers': self.get_header_json(),
            'row_spec': self.get_row_spec(),
            'rows': list(map(self.form_to_json, self.child_forms)),
            'errors': getattr(self, 'errors', False),
            'csrf_token': get_token(self.request),
        }

    def as_table(self):
        return render_to_string(self.template, self.get_context())


class HQAuthenticationTokenForm(AuthenticationTokenForm):
    def __init__(self, user, initial_device, request, **kwargs):
        super().__init__(user, initial_device, **kwargs)
        self.request = request

    def clean(self):
        try:
            cleaned_data = super(HQAuthenticationTokenForm, self).clean()
        except ValidationError:
            user_login_failed.send(sender=__name__, credentials={'username': self.user.username},
                request=self.request,
                token_failure=True)
            couch_user = CouchUser.get_by_username(self.user.username)
            if couch_user and couch_user.is_locked_out():
                metrics_counter('commcare.auth.token_lockout')
                raise ValidationError(LOCKOUT_MESSAGE)
            else:
                raise

        # Handle the edge-case where the user enters a correct token
        # after being locked out
        couch_user = CouchUser.get_by_username(self.user.username)
        if couch_user and couch_user.is_locked_out():
            metrics_counter('commcare.auth.lockouts')
            raise ValidationError(LOCKOUT_MESSAGE)
        return cleaned_data


class HQBackupTokenForm(BackupTokenForm):

    def __init__(self, user, initial_device, request, **kwargs):
        super().__init__(user, initial_device, **kwargs)
        self.request = request

    def clean(self):
        try:
            cleaned_data = super(HQBackupTokenForm, self).clean()
        except ValidationError:
            user_login_failed.send(sender=__name__, credentials={'username': self.user.username},
                request=self.request,
                token_failure=True)
            couch_user = CouchUser.get_by_username(self.user.username)
            if couch_user and couch_user.is_locked_out():
                metrics_counter('commcare.auth.token_lockout')
                raise ValidationError(LOCKOUT_MESSAGE)
            else:
                raise

        # Handle the edge-case where the user enters a correct token
        # after being locked out
        couch_user = CouchUser.get_by_username(self.user.username)
        if couch_user and couch_user.is_locked_out():
            metrics_counter('commcare.auth.lockouts')
            raise ValidationError(LOCKOUT_MESSAGE)
        return cleaned_data
