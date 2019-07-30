from __future__ import absolute_import
from __future__ import unicode_literals
import json

import six
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.middleware.csrf import get_token
from django.http import QueryDict
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe

from corehq.apps.domain.forms import NoAutocompleteMixin
from corehq.apps.users.models import CouchUser

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton, InlineField
from crispy_forms.helper import FormHelper

from memoized import memoized
from six.moves import map


class EmailAuthenticationForm(NoAutocompleteMixin, AuthenticationForm):
    username = forms.EmailField(label=_("E-mail"), max_length=75,
                                widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    def clean_username(self):
        username = self.cleaned_data.get('username', '').lower()
        return username

    def clean_password(self):
        from corehq.apps.hqwebapp.utils import decode_password
        # decode password submitted from HQ login
        # also pass in username to track replay attack
        return decode_password(self.cleaned_data['password'], self.clean_username())

    def clean(self):
        lockout_message = mark_safe(_('Sorry - you have attempted to login with an incorrect password too many times. Please <a href="/accounts/password_reset_email/">click here</a> to reset your password or contact the domain administrator.'))

        username = self.cleaned_data.get('username')
        if username is None:
            raise ValidationError(_('Please enter a valid email address.'))

        password = self.cleaned_data.get('password')
        if not password:
            raise ValidationError(_("Please enter a password."))

        try:
            cleaned_data = super(EmailAuthenticationForm, self).clean()
        except ValidationError:
            user = CouchUser.get_by_username(username)
            if user and user.is_locked_out() and user.supports_lockout():
                raise ValidationError(lockout_message)
            else:
                raise
        user = CouchUser.get_by_username(username)
        if user and user.is_locked_out() and user.supports_lockout():
            raise ValidationError(lockout_message)
        return cleaned_data


class CloudCareAuthenticationForm(EmailAuthenticationForm):
    username = forms.CharField(label=_("Username"), max_length=75,
                               widget=forms.TextInput(attrs={'class': 'form-control'}))


class BulkUploadForm(forms.Form):
    bulk_upload_file = forms.FileField(label="")
    action = forms.CharField(widget=forms.HiddenInput(), initial='bulk_upload')

    def __init__(self, plural_noun, action, form_id, context, *args, **kwargs):
        super(BulkUploadForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
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
                ('<i class="fa fa-cloud-upload"></i> Upload %s' % plural_noun),
                css_class='btn-primary',
                data_bind='disable: !file()',
                onclick='this.disabled=true;this.form.submit();',
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
    template = "hqwebapp/partials/form_list_form.html"

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
                                      .format(six.text_type(e)))
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
