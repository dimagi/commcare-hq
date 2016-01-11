from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy

from corehq.apps.es.users import UserES
from corehq.apps.hqcase.dbaccessors import get_case_types_for_domain
from corehq.apps.repeaters.models import RegisterGenerator
from corehq.apps.style import crispy as hqcrispy
from corehq.apps.users.util import raw_username

from dimagi.utils.decorators.memoized import memoized


class GenericRepeaterForm(forms.Form):

    url = forms.URLField(
        required=True,
        label='URL to forward to',
        help_text='Please enter the full url, like http://www.example.com/forwarding/',
        widget=forms.TextInput(attrs={"class": "url"})
    )
    use_basic_auth = forms.BooleanField(
        required=False,
        label='Use basic authentication?',
    )
    username = forms.CharField(
        required=False,
        label='Username',
    )
    password = forms.CharField(
        required=False,
        label='Password',
        widget=forms.PasswordInput()
    )

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain')
        self.repeater_class = kwargs.pop('repeater_class')
        self.formats = RegisterGenerator.all_formats_by_repeater(self.repeater_class, for_domain=self.domain)
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
                    _("Start Forwarding"),
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
            self.special_crispy_fields["use_basic_auth"],
            "username",
            "password"
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
                        css_class='btn btn-info disabled',
                    ),
                    crispy.Div(
                        css_id='test-forward-result',
                        css_class='text-success hide',
                    ),
                    css_class='{} {}'.format(self.helper.field_class, self.helper.offset_class),
                ),
                css_class='form-group'
            ),
            "use_basic_auth": twbscrispy.PrependedText('use_basic_auth', ''),
        }

    def clean(self):
        cleaned_data = super(GenericRepeaterForm, self).clean()
        if 'format' not in cleaned_data:
            cleaned_data['format'] = self.formats[0][0]

        return cleaned_data


class FormRepeaterForm(GenericRepeaterForm):
    exclude_device_reports = forms.BooleanField(
        required=False,
        label='Exclude device reports',
        initial=True
    )
    include_app_id_param = forms.BooleanField(
        required=False,
        label="Include 'app_id' URL query parameter.",
        initial=True
    )

    def get_ordered_crispy_form_fields(self):
        fields = super(FormRepeaterForm, self).get_ordered_crispy_form_fields()
        fields.extend([
            twbscrispy.PrependedText('exclude_device_reports', ''),
            twbscrispy.PrependedText('include_app_id_param', '')
        ])
        return fields


class CaseRepeaterForm(GenericRepeaterForm):
    white_listed_case_types = forms.MultipleChoiceField(
        required=False,
        label=_('Case Types'),
        help_text=_('Only cases of this type will be forwarded. Leave empty to forward all cases')
    )
    black_listed_users = forms.MultipleChoiceField(
        required=False,
        label=_('Users to exclude'),
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
        return ['white_listed_case_types'] + ['black_listed_users'] + fields

    def clean(self):
        cleaned_data = super(GenericRepeaterForm, self).clean()
        white_listed_case_types = cleaned_data['white_listed_case_types']
        black_listed_users = cleaned_data['black_listed_users']
        if not set(white_listed_case_types).issubset([t[0] for t in self.case_type_choices]):
            raise ValidationError(_('Unknown case-type'))
        if not set(black_listed_users).issubset([t[0] for t in self.user_choices]):
            raise ValidationError(_('Unknown user'))
        return cleaned_data
