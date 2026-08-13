import json
from datetime import datetime, timedelta

from django import forms
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import BootstrapSwitchInput
from corehq.apps.public_webforms.endpoints import (
    create_public_webform_endpoint,
    delete_public_webform_build,
)
from corehq.apps.public_webforms.form_choices import (
    get_public_webform_choices,
    get_public_webform_eligible_form,
    get_public_webform_type,
)
from corehq.apps.public_webforms.models import PublicWebform
from corehq.util.timezones.conversions import ServerTime, UserTime


class CreatePublicWebformForm(forms.Form):
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
    app_id = forms.CharField(required=False, widget=forms.HiddenInput)
    form_unique_id = forms.CharField(required=False, widget=forms.HiddenInput)

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

        default_expires_at = (
            ServerTime(datetime.now()).user_time(self.timezone).done()
            + timedelta(days=30)
        )
        self.fields['expires_at'].initial = default_expires_at.strftime('%Y-%m-%d %H:%M:%S')

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'

        alpine_data_model = {
            'expires_at': self.fields['expires_at'].initial,
        }
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("New Public Webform"),
                crispy.HTML(render_to_string(
                    'public_webforms/partials/create_form_choices.html',
                    context={'form_choices': json.dumps(get_public_webform_choices(self.domain))},
                )),
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
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    hqcrispy.LinkButton(
                        _("Cancel"),
                        reverse('manage_public_webforms', args=[self.domain]),
                        css_class='btn btn-outline-primary',
                    ),
                    crispy.Submit(
                        'create_public_webform',
                        _("Create Public Webform"),
                        css_class='disable-on-submit',
                    ),
                )
            ),
        )

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

    def clean_expires_at(self):
        # The datepicker submits wall-clock time in the project's timezone; store UTC.
        expires_at = self.cleaned_data['expires_at']
        return UserTime(expires_at, tzinfo=self.timezone).server_time().done()

    def create_public_webform(self):
        app_id = self.cleaned_data['app_id']
        form_unique_id = self.cleaned_data['form_unique_id']
        app_build_id, endpoint_id = create_public_webform_endpoint(
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
