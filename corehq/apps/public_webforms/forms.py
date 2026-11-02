import json
from datetime import datetime, timedelta, UTC

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from django import forms
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import BootstrapSwitchInput
from corehq.apps.public_webforms.app_builds import (
    create_public_webform_build,
    delete_public_webform_build,
)
from corehq.apps.public_webforms.form_choices import (
    get_public_webform_choices,
    get_public_webform_type,
)
from corehq.apps.public_webforms.form_paths import (
    get_public_webform_form_paths,
)
from corehq.apps.public_webforms.models import (
    PublicWebform,
    PublicWebformStatus,
    PublicWebformType,
)
from corehq.apps.public_webforms.utils import get_public_webform_eligible_form
from corehq.apps.sms.util import domain_can_send_sms
from corehq.util.timezones.conversions import ServerTime, UserTime

ALPINE_DATETIME_PICKER_FORMAT = '%Y-%m-%d %H:%M:%S'


class PublicWebformFilterForm(forms.Form):

    search = forms.CharField(
        required=False,
        label=gettext_lazy("Search labels"),
        widget=forms.TextInput(attrs={
            'type': 'search',
            'class': 'form-control',
            'placeholder': gettext_lazy("Search labels"),
        }),
    )
    status = forms.ChoiceField(
        required=False,
        label=gettext_lazy("Status"),
        choices=[('', gettext_lazy("Any status"))] + PublicWebformStatus.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    session_type = forms.ChoiceField(
        required=False,
        label=gettext_lazy("Type"),
        choices=[('', gettext_lazy("Any type"))] + PublicWebformType.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    lookups = {
        'search': 'label__icontains',
        'status': 'status',
        'session_type': 'session_type',
    }

    def filter(self, queryset):
        self.is_valid()
        for field, lookup in self.lookups.items():
            if value := self.cleaned_data.get(field):
                queryset = queryset.filter(**{lookup: value})
        return queryset

    @property
    def is_filtering(self):
        self.is_valid()
        return any(self.cleaned_data.get(field) for field in self.lookups)


class BasePublicWebformForm(forms.Form):

    fieldset_title = None
    submit_name = None
    submit_label = None

    label = forms.CharField(
        label=gettext_lazy("Label"),
        help_text=gettext_lazy("Identifies this public webform. Respondents will see the form's name.")
    )
    expires_at = forms.DateTimeField(
        label=gettext_lazy("Close Requests At"),
        help_text=gettext_lazy(
            "The public request page closes at this time. "
            "One-time links already sent can be used until they expire."
        ),
    )
    allow_email = forms.BooleanField(
        label=gettext_lazy("Email"),
        help_text=gettext_lazy("A branded email with a single-use link."),
        initial=True,
        required=False,
    )
    allow_sms = forms.BooleanField(
        label=gettext_lazy("SMS"),
        help_text=gettext_lazy("A short text with a shortened link. Billed per message sent."),
        required=False,
    )
    open_to_requests = forms.BooleanField(
        required=False,
        label=gettext_lazy("Open to Requests"),
        widget=BootstrapSwitchInput(
            inline_label=gettext_lazy(
                "Immediately open this public webform to one-time link requests."
            ),
        ),
    )

    def __init__(self, domain, timezone, *args, **kwargs):
        self.domain = domain
        self.timezone = timezone
        super().__init__(*args, **kwargs)

        if not domain_can_send_sms(domain):
            self.fields['allow_sms'].disabled = True

        self.fields['expires_at'].initial = self.initial_expires_at()

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                self.fieldset_title,
                *self.fieldset_fields(),
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    hqcrispy.LinkButton(
                        _("Cancel"),
                        reverse('manage_public_webforms', args=[self.domain]),
                        css_class='btn btn-outline-primary',
                    ),
                    crispy.Submit(
                        self.submit_name,
                        self.submit_label,
                        css_class='disable-on-submit',
                    ),
                )
            ),
        )

    def initial_expires_at(self):
        """Wall-clock datetime in the project's timezone to prefill the picker."""
        raise NotImplementedError

    def fieldset_fields(self):
        alpine_data_model = {
            'expires_at': self.fields['expires_at'].initial,
        }
        allow_sms_field = [
            twbscrispy.InlineField('allow_sms'),
            crispy.HTML(
                format_html(
                    '<div class="form-text">{}</div>',
                    self.fields['allow_sms'].help_text,
                ),
            ),
        ]
        if self.fields['allow_sms'].disabled:
            allow_sms_field.append(
                crispy.HTML('{% include "public_webforms/partials/enable_messaging.html" %}'),
            )

        return [
            crispy.Field('label'),
            crispy.Div(
                twbscrispy.AppendedText(
                    'expires_at',
                    mark_safe(  # nosec: no user input
                        '<i class="fcc fcc-fd-datetime"></i>'
                    ),
                    x_datepicker=json.dumps(
                        {
                            'useInputGroup': True,
                            'datetime': True,
                        }
                    ),
                ),
                x_data=json.dumps(alpine_data_model),
            ),
            crispy.Div(
                crispy.HTML(
                    format_html(
                        '<label id="delivery-options-label" class="field-label">'
                        '{}<span class="asteriskField">*</span></label>',
                        _("How Respondents Receive Their One-time Link"),
                    ),
                ),
                crispy.Div(
                    twbscrispy.InlineField('allow_email'),
                    crispy.HTML(
                        format_html(
                            '<div class="form-text">{}</div>',
                            self.fields['allow_email'].help_text,
                        ),
                    ),
                    *allow_sms_field,
                    css_class='field-control',
                ),
                css_class='row mb-3',
                role='group',
                aria_labelledby='delivery-options-label',
            ),
            twbscrispy.PrependedText('open_to_requests', ''),
        ]

    def clean_expires_at(self):
        # The datepicker submits wall-clock time in the project's timezone; store UTC.
        user_time = UserTime(self.cleaned_data['expires_at'], tzinfo=self.timezone)
        expires_at = user_time.server_time().done()
        is_changed = user_time.ui_string(fmt=ALPINE_DATETIME_PICKER_FORMAT) != self.initial_expires_at()
        if is_changed and expires_at <= datetime.now(UTC).replace(tzinfo=None):
            raise forms.ValidationError(_("Webform must expire in the future."))
        return expires_at

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('allow_email') and not cleaned_data.get('allow_sms'):
            self.add_error(None, _("Choose at least one way for respondents to receive one-time links."))
        return cleaned_data


class CreatePublicWebformForm(BasePublicWebformForm):

    fieldset_title = gettext_lazy("New Public Webform")
    submit_name = 'create_public_webform'
    submit_label = gettext_lazy("Create Public Webform")

    app_id = forms.CharField(required=False, widget=forms.HiddenInput)
    menu_id = forms.CharField(required=False, widget=forms.HiddenInput)
    form_unique_id = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, domain, timezone, *args, app_id=None, form_unique_id=None, **kwargs):
        form = (
            get_public_webform_eligible_form(domain, app_id, form_unique_id)
            if app_id and form_unique_id else None
        )
        initial = {
            'app_id': app_id,
            'menu_id': form.get_module().unique_id,
            'form_unique_id': form_unique_id,
        } if form else {}
        super().__init__(domain, timezone, *args, initial=initial, **kwargs)

    def initial_expires_at(self):
        return (
            ServerTime(datetime.now(UTC).replace(tzinfo=None) + timedelta(days=90))
            .user_time(self.timezone)
            .ui_string(fmt=ALPINE_DATETIME_PICKER_FORMAT)
        )

    def fieldset_fields(self):
        form_choices = {
            'apps': get_public_webform_choices(self.domain),
            'appId': self['app_id'].value() or '',
            'menuId': self['menu_id'].value() or '',
            'formId': self['form_unique_id'].value() or '',
        }
        return [
            crispy.HTML(render_to_string(
                'public_webforms/partials/create_form_choices.html',
                context={'form_choices': json.dumps(form_choices)},
            )),
            *super().fieldset_fields(),
        ]

    def clean(self):
        cleaned_data = super().clean()
        app_id = cleaned_data.get('app_id')
        form_unique_id = cleaned_data.get('form_unique_id')
        form = (
            get_public_webform_eligible_form(self.domain, app_id, form_unique_id)
            if app_id and form_unique_id else None
        )
        if not form:
            raise forms.ValidationError(_("Please select an application, menu, and form."))

        cleaned_data['session_type'] = get_public_webform_type(form)
        return cleaned_data

    def create_public_webform(self):
        app_id = self.cleaned_data['app_id']
        form_unique_id = self.cleaned_data['form_unique_id']
        app_build_id, endpoint_id = create_public_webform_build(
            self.domain, app_id, form_unique_id)
        try:
            return PublicWebform.objects.create(
                domain=self.domain,
                label=self.cleaned_data['label'],
                app_id=app_id,
                app_build_id=app_build_id,
                form_unique_id=form_unique_id,
                endpoint_id=endpoint_id,
                session_type=self.cleaned_data['session_type'],
                expires_at=self.cleaned_data['expires_at'],
                allow_email=self.cleaned_data['allow_email'],
                allow_sms=self.cleaned_data['allow_sms'],
                is_disabled=not self.cleaned_data['open_to_requests'],
            )
        except Exception:
            # The build is written to Couch and the webform to SQL; ensure we
            # delete the build on webform create failure.
            delete_public_webform_build(self.domain, app_build_id)
            raise


class EditPublicWebformForm(BasePublicWebformForm):

    fieldset_title = gettext_lazy("Edit Public Webform")
    submit_name = 'edit_public_webform'
    submit_label = gettext_lazy("Save Changes")

    app_name = forms.CharField(
        label=gettext_lazy("Application"), disabled=True, required=False)
    menu_name = forms.CharField(
        label=gettext_lazy("Menu"), disabled=True, required=False)
    form_name = forms.CharField(
        label=gettext_lazy("Form"), disabled=True, required=False)

    def __init__(self, domain, timezone, webform, *args, **kwargs):
        self.webform = webform
        super().__init__(domain, timezone, *args, **kwargs)
        form_paths = get_public_webform_form_paths(
            domain, [webform])[webform.id]
        if form_paths['is_app_deleted']:
            self.fields['open_to_requests'].disabled = True
            self.fields['open_to_requests'].help_text = _(
                "This webform's application has been deleted, so it can't be opened.")
        self.initial.update({
            'label': webform.label,
            'open_to_requests': not webform.is_disabled and not form_paths['is_app_deleted'],
            'app_name': f"{form_paths['app_name']} (v{form_paths['app_version']})",
            'menu_name': form_paths['menu_name'],
            'form_name': form_paths['form_name'],
            'allow_email': webform.allow_email,
            'allow_sms': webform.allow_sms and not self.fields['allow_sms'].disabled,
        })

    def initial_expires_at(self):
        return (
            ServerTime(self.webform.expires_at)
            .user_time(self.timezone)
            .ui_string(fmt=ALPINE_DATETIME_PICKER_FORMAT)
        )

    def fieldset_fields(self):
        return [
            crispy.Field('app_name'),
            crispy.Field('menu_name'),
            crispy.Field('form_name'),
            *super().fieldset_fields(),
        ]

    def update_public_webform(self):
        self.webform.label = self.cleaned_data['label']
        self.webform.expires_at = self.cleaned_data['expires_at']
        self.webform.allow_email = self.cleaned_data['allow_email']
        self.webform.allow_sms = self.cleaned_data['allow_sms']
        self.webform.set_disabled(not self.cleaned_data['open_to_requests'])
        self.webform.save()
        return self.webform
