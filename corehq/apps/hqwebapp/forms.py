import json

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label=_("E-mail"), max_length=75)

    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        return username


class CloudCareAuthenticationForm(EmailAuthenticationForm):
    username = forms.EmailField(label=_("Username"), max_length=75)


class BulkUploadForm(forms.Form):
    bulk_upload_file = forms.FileField(label="")
    action = forms.CharField(widget=forms.HiddenInput(), initial='bulk_upload')

    def __init__(self, plural_noun, action, form_id, *args, **kwargs):
        super(BulkUploadForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = form_id
        self.helper.form_method = 'post'
        if action:
            self.helper.form_action = action
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                "",
                crispy.Field(
                    'bulk_upload_file',
                    data_bind="value: file",
                ),
                crispy.Field(
                    'action',
                ),
            ),
            StrictButton(
                ('<i class="icon-cloud-upload"></i> Upload %s'
                 % plural_noun.title()),
                css_class='btn-primary',
                data_bind='disable: !file()',
                onclick='this.disabled=true;this.form.submit();',
                type='submit',
            ),
        )


class FormListForm(object):
    """
    A higher-level form for editing an arbitrary number of instances of one
    sub-form in a tabular fashion.
    Give your child_form_class a `slug` field to enforce uniqueness

    API:
        is_valid
        cleaned_data
        errors
        as_table

    # TODO document header config
    """
    child_form_class = None  # Django form which controls each row
    # child_form_template = None
    # sortable = False
    # deletable = False
    # can_add_elements = False
    columns = None  # list configuring the columns to display

    child_form_data = forms.CharField(widget=forms.HiddenInput)
    template = "hqwebapp/partials/form_list_form.html"

    def __init__(self, data=None, *args, **kwargs):
        if self.child_form_class is None:
            raise NotImplementedError("You must specify a child form to use"
                                      "for each row")
        if self.columns is None:
            raise NotImplementedError("You must specify columns for your table")

        self.child_forms = []
        for row in data:
            self.child_forms.append(self.child_form_class(row, *args, **kwargs))

    def clean_child_forms(self):
        """
        Populates self.errors and self.cleaned_data
        """
        # TODO use self.child_forms here
        raw_child_form_data = json.loads(self.cleaned_data['child_form_data'])
        self.errors = False
        self.cleaned_data = []
        for raw_child_form in raw_child_form_data:
            child_form = self.child_form_class(raw_child_form)
            child_form.is_valid()
            self.cleaned_data.append(child_form.cleaned_data)
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
                columns.append({'type': field.widget.__class__.__name__,
                                'key': header})
        return columns

    def form_to_json(self, form):
        """
        Converts a child form to JSON for rendering
        """
        json_row = {}
        for header in self.columns:
            if isinstance(header, dict):
                # form.data should contain everything passed to the form
                # constructor
                json_row[header['key']] = form.data.get(header['key'])
            elif isinstance(self.get_child_form_field(header), forms.Field):
                json_row[header] = form.data.get(header)
        return json_row

    def get_context(self):
        return {
            'headers': self.get_header_json(),
            'row_spec': self.get_row_spec(),
            'rows': map(self.form_to_json, self.child_forms),
        }

    def as_table(self):
        return render_to_string(self.template, self.get_context())
