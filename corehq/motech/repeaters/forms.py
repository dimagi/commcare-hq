from __future__ import absolute_import
from __future__ import unicode_literals
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from corehq.apps.locations.forms import LocationSelectWidget
from corehq.motech.repeaters.dbaccessors import get_repeaters_by_domain
from corehq.motech.repeaters.repeater_generators import RegisterGenerator
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain_es
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy

from corehq.apps.es.users import UserES
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.users.util import raw_username

from memoized import memoized

from .models import BASIC_AUTH, DIGEST_AUTH


class GenericRepeaterForm(forms.Form):

    url = forms.URLField(
        required=True,
        label='URL to forward to',
        help_text='Please enter the full url, like http://www.example.com/forwarding/',
        widget=forms.TextInput(attrs={"class": "url"})
    )
    auth_type = forms.ChoiceField(
        choices=[
            (None, "None"),
            (BASIC_AUTH, "Basic"),
            (DIGEST_AUTH, "Digest"),
        ],
        required=False,
        label=_("Authentication protocol"),
    )
    username = forms.CharField(
        required=False,
        label='Username',
    )
    password = forms.CharField(
        required=False,
        label='Password',
        widget=forms.PasswordInput(render_value=True)
    )
    skip_cert_verify = forms.BooleanField(
        label=_('Skip SSL certificate verification'),
        required=False,
        help_text=_('FOR TESTING ONLY: DO NOT ENABLE THIS FOR PRODUCTION INTEGRATIONS'),
    )

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain')
        self.repeater_class = kwargs.pop('repeater_class')
        self.formats = RegisterGenerator.all_formats_by_repeater(self.repeater_class, for_domain=self.domain)
        self.submit_btn_text = kwargs.pop('submit_btn_text', _("Start Forwarding"))
        super(GenericRepeaterForm, self).__init__(*args, **kwargs)

        self.set_extra_django_form_fields()
        self._initialize_crispy_layout()

    def set_extra_django_form_fields(self):
        """
        Override this to set extra django form-fields that can be calculated only within request context
        """
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
        form_fields = []
        if self.formats and len(self.formats) > 1:
            form_fields = ['format']

        form_fields.extend([
            "url",
            self.special_crispy_fields["test_link"],
            self.special_crispy_fields["auth_type"],
            "username",
            "password",
            self.special_crispy_fields["skip_cert_verify"],
        ])
        return form_fields

    @property
    def special_crispy_fields(self):
        """
        DRY mapping that can be used in generating self.get_ordered_crispy_form_fields
        """
        return {
            "test_link": crispy.Div(
                crispy.Div(
                    twbscrispy.StrictButton(
                        _('Test Link'),
                        type='button',
                        css_id='test-forward-link',
                        css_class='btn btn-default disabled',
                    ),
                    crispy.Div(
                        css_id='test-forward-result',
                        css_class='text-success hide',
                    ),
                    css_class='{} {}'.format(self.helper.field_class, self.helper.offset_class),
                ),
                css_class='form-group'
            ),
            "auth_type": twbscrispy.PrependedText('auth_type', ''),
            "skip_cert_verify": twbscrispy.PrependedText('skip_cert_verify', ''),
        }

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

    def get_ordered_crispy_form_fields(self):
        fields = super(FormRepeaterForm, self).get_ordered_crispy_form_fields()
        fields.extend([
            twbscrispy.PrependedText('include_app_id_param', '')
        ])
        return fields


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
        return [(t, t) for t in get_case_types_for_domain_es(self.domain)]

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
        return ['white_listed_case_types'] + ['black_listed_users'] + fields

    def clean(self):
        cleaned_data = super(CaseRepeaterForm, self).clean()
        white_listed_case_types = cleaned_data.get('white_listed_case_types', [])
        black_listed_users = cleaned_data.get('black_listed_users', [])
        if not set(white_listed_case_types).issubset([t[0] for t in self.case_type_choices]):
            raise ValidationError(_('Unknown case-type'))
        if not set(black_listed_users).issubset([t[0] for t in self.user_choices]):
            raise ValidationError(_('Unknown user'))
        return cleaned_data


class OpenmrsRepeaterForm(CaseRepeaterForm):
    location_id = forms.CharField(
        label=_("Location"),
        required=False,
        help_text=_(
            'Cases at this location and below will be forwarded. '
            'Leave empty if this is the only OpenMRS Forwarder'
        )
    )
    atom_feed_enabled = forms.BooleanField(
        label=_('Atom feed enabled'),
        required=False,
        help_text=_('Poll Atom feed for changes made in OpenMRS/Bahmni'),
    )

    def __init__(self, *args, **kwargs):
        super(OpenmrsRepeaterForm, self).__init__(*args, **kwargs)
        self.fields['location_id'].widget = LocationSelectWidget(self.domain, id='id_location_id')

    def get_ordered_crispy_form_fields(self):
        fields = super(OpenmrsRepeaterForm, self).get_ordered_crispy_form_fields()
        return [
            'location_id',
            twbscrispy.PrependedText('atom_feed_enabled', ''),
        ] + fields

    def clean(self):
        cleaned_data = super(OpenmrsRepeaterForm, self).clean()
        white_listed_case_types = cleaned_data.get('white_listed_case_types', [])
        atom_feed_enabled = cleaned_data.get('atom_feed_enabled', False)
        location_id = cleaned_data.get('location_id', None)
        if atom_feed_enabled:
            if len(white_listed_case_types) != 1:
                raise ValidationError(_(
                    'Specify a single case type so that CommCare can add cases using the Atom feed for patients '
                    'created in OpenMRS/Bahmni.'
                ))
            if not location_id:
                raise ValidationError(_(
                    'Specify a location so that CommCare can set an owner for cases added via the Atom feed.'
                ))
        return cleaned_data


class Dhis2RepeaterForm(FormRepeaterForm):

    def __init__(self, *args, **kwargs):
        super(Dhis2RepeaterForm, self).__init__(*args, **kwargs)
        # self.fields['location_id'].widget = SupplyPointSelectWidget(self.domain, id='id_location_id')

    def get_ordered_crispy_form_fields(self):
        fields = super(Dhis2RepeaterForm, self).get_ordered_crispy_form_fields()
        return fields


class EmailBulkPayload(forms.Form):
    repeater_id = forms.ChoiceField(label=_("Repeater"))
    payload_ids_file = forms.FileField(
        label=_("Payload IDs"),
        required=True,
    )
    email_id = forms.EmailField(
        label=_("Email ID"),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain')
        super(EmailBulkPayload, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-10'
        self.helper.offset_class = 'col-sm-offset-3 col-md-offset-2'
        self.fields['repeater_id'].choices = \
            [(repeater.get_id, '{}: {}'.format(
                repeater.doc_type,
                repeater.url,
            )) for repeater in get_repeaters_by_domain(self.domain)]
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Email Bulk Payload"),
                crispy.Field('repeater_id'),
                crispy.Field('payload_ids_file'),
                crispy.Field('email_id'),
                twbscrispy.StrictButton(
                    _("Email Payloads"),
                    type="submit",
                    css_class='btn-primary',
                )
            )
        )
