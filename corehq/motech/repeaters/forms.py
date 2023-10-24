from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from memoized import memoized

from corehq.apps.es.users import UserES
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain
from corehq.apps.users.util import raw_username
from corehq.motech.const import REQUEST_METHODS, REQUEST_POST
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.repeater_generators import RegisterGenerator
from corehq.motech.views import ConnectionSettingsListView


class GenericRepeaterForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.repeater_name = ""
        data = kwargs.get('data')
        if data:
            self.repeater_name = data.get("name")

        self.domain = kwargs.pop('domain')
        self.repeater_class = kwargs.pop('repeater_class')
        self.formats = RegisterGenerator.all_formats_by_repeater(self.repeater_class, for_domain=self.domain)
        conns = ConnectionSettings.objects.filter(domain=self.domain)
        self.connection_settings_choices = [(c.id, c.name) for c in conns]
        self.submit_btn_text = kwargs.pop('submit_btn_text', _("Start Forwarding"))
        super(GenericRepeaterForm, self).__init__(*args, **kwargs)

        self.set_extra_django_form_fields()
        self._initialize_crispy_layout()

    def set_extra_django_form_fields(self):
        """
        Override this to set extra django form-fields that can be calculated only within request context
        """
        url = reverse(
            ConnectionSettingsListView.urlname,
            kwargs={'domain': self.domain},
        )
        self.fields['connection_settings_id'] = forms.ChoiceField(
            label=_("Connection Settings"),
            choices=self.connection_settings_choices,
            required=True,
            help_text=_(f'<a href="{url}">Add/Edit Connections Settings</a>')
        )
        self.fields['name'] = forms.CharField(
            label=_('Name'),
            help_text='The name of this forwarder',
            initial=self.repeater_name,
            required=False
        )
        self.fields['request_method'] = forms.ChoiceField(
            label=_("HTTP Request Method"),
            choices=[(rm, rm) for rm in REQUEST_METHODS],
            initial=REQUEST_POST,
            required=True,
        )
        if self.formats and len(self.formats) > 1:
            self.fields['format'] = forms.ChoiceField(
                required=True,
                label='Payload Format',
                choices=self.formats,
            )

    def _initialize_crispy_layout(self):
        self.helper = FormHelper(self)
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.offset_class = 'col-sm-offset-3 col-md-offset-2'

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Forwarding Settings',
                *self.get_ordered_crispy_form_fields()
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    self.submit_btn_text,
                    type="submit",
                    css_class='btn-primary',
                )
            )
        )

    def get_ordered_crispy_form_fields(self):
        """
        Override this to change the order of the crispy form fields and add extra crispy fields
        """
        form_fields = ["connection_settings_id", "name", "request_method"]
        if self.formats and len(self.formats) > 1:
            form_fields.append('format')
        return form_fields

    def clean(self):
        cleaned_data = super(GenericRepeaterForm, self).clean()
        if 'format' not in cleaned_data:
            cleaned_data['format'] = self.formats[0][0]

        return cleaned_data


class FormRepeaterForm(GenericRepeaterForm):
    include_app_id_param = forms.BooleanField(
        required=False,
        label="Include 'app_id' URL query parameter.",
        initial=True
    )
    user_blocklist = forms.MultipleChoiceField(
        required=False,
        label=_('Users to exclude'),
        widget=forms.SelectMultiple(attrs={'class': 'hqwebapp-select2'}),
        help_text=_('Forms submitted by these users will not be forwarded')
    )
    white_listed_form_xmlns = forms.CharField(
        required=False,
        label=_('XMLNSes of forms to include'),
        widget=forms.Textarea(),
        help_text=_(
            'Separate with commas, spaces or newlines. Leave empty to forward '
            'all forms.'
        ),
    )

    def __init__(self, *args, **kwargs):
        if 'data' in kwargs and 'white_listed_form_xmlns' in kwargs['data']:
            # `FormRepeater.white_listed_form_xmlns` is a list, but
            # `FormRepeaterForm.white_listed_form_xmlns` takes a string.
            xmlns_list = kwargs['data']['white_listed_form_xmlns']
            kwargs['data']['white_listed_form_xmlns'] = ', \n'.join(xmlns_list)
        super().__init__(*args, **kwargs)

    @property
    @memoized
    def user_choices(self):
        users = UserES().domain(self.domain).fields(['_id', 'username']).run().hits
        return [(user['_id'], raw_username(user['username'])) for user in users]

    def set_extra_django_form_fields(self):
        super(FormRepeaterForm, self).set_extra_django_form_fields()
        self.fields['user_blocklist'].choices = self.user_choices

    def get_ordered_crispy_form_fields(self):
        fields = super(FormRepeaterForm, self).get_ordered_crispy_form_fields()
        return fields + [
            twbscrispy.PrependedText('include_app_id_param', ''),
            'user_blocklist',
            'white_listed_form_xmlns',
        ]


class CaseRepeaterForm(GenericRepeaterForm):
    white_listed_case_types = forms.MultipleChoiceField(
        required=False,
        label=_('Case Types'),
        widget=forms.SelectMultiple(attrs={'class': 'hqwebapp-select2'}),
        help_text=_('Only cases of this type will be forwarded. Leave empty to forward all cases')
    )
    black_listed_users = forms.MultipleChoiceField(
        required=False,
        label=_('Users to exclude'),
        widget=forms.SelectMultiple(attrs={'class': 'hqwebapp-select2'}),
        help_text=_('Case creations and updates submitted by these users will not be forwarded')
    )

    @property
    @memoized
    def case_type_choices(self):
        return [(t, t) for t in get_case_types_for_domain(self.domain)]

    @property
    @memoized
    def user_choices(self):
        users = UserES().domain(self.domain).fields(['_id', 'username']).run().hits
        return [(user['_id'], raw_username(user['username'])) for user in users]

    def set_extra_django_form_fields(self):
        super(CaseRepeaterForm, self).set_extra_django_form_fields()
        self.fields['white_listed_case_types'].choices = self.case_type_choices
        self.fields['black_listed_users'].choices = self.user_choices

    def get_ordered_crispy_form_fields(self):
        fields = super(CaseRepeaterForm, self).get_ordered_crispy_form_fields()
        return fields + ['white_listed_case_types', 'black_listed_users']

    def clean(self):
        cleaned_data = super(CaseRepeaterForm, self).clean()
        white_listed_case_types = cleaned_data.get('white_listed_case_types', [])
        black_listed_users = cleaned_data.get('black_listed_users', [])
        if not set(white_listed_case_types).issubset([t[0] for t in self.case_type_choices]):
            raise ValidationError(_('Unknown case-type'))
        if not set(black_listed_users).issubset([t[0] for t in self.user_choices]):
            raise ValidationError(_('Unknown user'))
        return cleaned_data
