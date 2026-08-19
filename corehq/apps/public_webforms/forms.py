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

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import BootstrapSwitchInput
from corehq.apps.public_webforms.app_builds import (
    create_public_webform_build,
    delete_public_webform_build,
)
from corehq.apps.public_webforms.form_choices import (
    get_public_webform_choices,
    get_public_webform_eligible_form,
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
from corehq.util.timezones.conversions import ServerTime, UserTime


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
        self.is_valid()  # populates cleaned_data, dropping any invalid field
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
    link_choices = forms.MultipleChoiceField(
        label=gettext_lazy("How Respondents Receive Their One-time Link"),
        choices=[],
        initial=['allow_email'],
        widget=forms.CheckboxSelectMultiple,
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

        link_choices = [(
            'allow_email',
            format_html(
                '{} <div class="form-text">{}</div>',
                _("Email"),
                _("A branded email with a single-use link.")
            ),
        )]
        if domain_has_privilege(domain, privileges.OUTBOUND_SMS):
            link_choices.append((
                'allow_sms',
                format_html(
                    '{} <div class="form-text">{}</div>',
                    _("SMS"),
                    _("A short text with a shortened link. Billed per message sent.")
                ),
            ))

        self.fields['link_choices'].choices = link_choices

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
            crispy.Field('link_choices'),
            twbscrispy.PrependedText('open_to_requests', ''),
        ]

    def clean_expires_at(self):
        # The datepicker submits wall-clock time in the project's timezone; store UTC.
        expires_at = self.cleaned_data['expires_at']
        return UserTime(expires_at, tzinfo=self.timezone).server_time().done()


class CreatePublicWebformForm(BasePublicWebformForm):

    fieldset_title = gettext_lazy("New Public Webform")
    submit_name = 'create_public_webform'
    submit_label = gettext_lazy("Create Public Webform")

    app_id = forms.CharField(required=False, widget=forms.HiddenInput)
    form_unique_id = forms.CharField(required=False, widget=forms.HiddenInput)

    def initial_expires_at(self):
        return (
            ServerTime(datetime.now(UTC).replace(tzinfo=None) + timedelta(days=30))
            .user_time(self.timezone)
            .ui_string(fmt='%Y-%m-%d %H:%M:%S')
        )

    def fieldset_fields(self):
        return [
            crispy.HTML(render_to_string(
                'public_webforms/partials/create_form_choices.html',
                context={'form_choices': json.dumps(get_public_webform_choices(self.domain))},
            )),
            *super().fieldset_fields(),
        ]

    def clean(self):
        cleaned_data = super().clean()
        app_id = cleaned_data.get('app_id')
        form_unique_id = cleaned_data.get('form_unique_id')
        if not app_id or not form_unique_id:
            raise forms.ValidationError(_("Please select an application, menu, and form."))

        form = get_public_webform_eligible_form(self.domain, app_id, form_unique_id)
        if not form:
            raise forms.ValidationError(_(
                "The selected form can't be used for a public webform."
            ))

        cleaned_data['session_type'] = get_public_webform_type(form)
        return cleaned_data

    def create_public_webform(self):
        app_id = self.cleaned_data['app_id']
        form_unique_id = self.cleaned_data['form_unique_id']
        app_build_id, endpoint_id = create_public_webform_build(
            self.domain, app_id, form_unique_id)
        link_choices = self.cleaned_data['link_choices']
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
                allow_email='allow_email' in link_choices,
                allow_sms='allow_sms' in link_choices,
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
        self.initial.update({
            'label': webform.label,
            'open_to_requests': not webform.is_disabled,
            'app_name': f"{form_paths['app_name']} (v{form_paths['app_version']})",
            'menu_name': form_paths['menu_name'],
            'form_name': form_paths['form_name'],
            # a delivery option the project can no longer use is dropped, not kept
            'link_choices': [
                choice for choice, __ in self.fields['link_choices'].choices
                if getattr(webform, choice)
            ],
        })

    def initial_expires_at(self):
        return ServerTime(self.webform.expires_at).user_time(self.timezone).ui_string(fmt='%Y-%m-%d %H:%M:%S')

    def fieldset_fields(self):
        return [
            crispy.Field('app_name'),
            crispy.Field('menu_name'),
            crispy.Field('form_name'),
            *super().fieldset_fields(),
        ]

    def update_public_webform(self):
        link_choices = self.cleaned_data['link_choices']
        self.webform.label = self.cleaned_data['label']
        self.webform.expires_at = self.cleaned_data['expires_at']
        self.webform.allow_email = 'allow_email' in link_choices
        self.webform.allow_sms = 'allow_sms' in link_choices
        self.webform.is_disabled = not self.cleaned_data['open_to_requests']
        self.webform.save()
        return self.webform
