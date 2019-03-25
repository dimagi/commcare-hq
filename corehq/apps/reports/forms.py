from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext
from corehq.apps.hqwebapp.crispy import FormActions, B3MultiField
import langcodes

from django import forms
from django.core.validators import MinLengthValidator
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from corehq.apps.hqwebapp.fields import MultiEmailField
from corehq.apps.hqwebapp.widgets import SelectToggle
from corehq.apps.userreports.reports.view import ConfigurableReportView
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from corehq.apps.saved_reports.models import ReportConfig, ReportNotification, \
    DEFAULT_REPORT_NOTIF_SUBJECT
from six.moves import range


class SavedReportConfigForm(forms.Form):
    name = forms.CharField()
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(),
    )
    start_date = forms.DateField(
        required=False,
    )
    end_date = forms.DateField(
        required=False,
    )
    datespan_slug = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )
    date_range = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )
    days = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
    )
    _id = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )
    report_slug = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )
    report_type = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )
    subreport_slug = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    def __init__(self, domain, user_id, *args, **kwargs):
        self.domain = domain
        self.user_id = user_id
        super(SavedReportConfigForm, self).__init__(*args, **kwargs)

    def clean(self):
        name = self.cleaned_data['name']
        _id = self.cleaned_data['_id']

        user_configs = ReportConfig.by_domain_and_owner(self.domain, self.user_id)
        if not _id and name in [c.name for c in user_configs]:
            raise forms.ValidationError(
                "A saved report with the name '%(name)s' already exists." % {
                    'name': name,
                }
            )

        date_range = self.cleaned_data['date_range']

        if (
            self.cleaned_data['report_type'] == ConfigurableReportView.prefix
            and not self.cleaned_data['datespan_slug']
        ):
            self.cleaned_data['date_range'] = None
        else:
            if date_range == 'last7':
                self.cleaned_data['days'] = 7
            elif date_range == 'last30':
                self.cleaned_data['days'] = 30
            elif (date_range == 'lastn' and self.cleaned_data.get('days') is None
                  and self.cleaned_data['report_type'] != ConfigurableReportView.prefix):
                raise forms.ValidationError(
                    "Field 'days' was expected but not provided."
                )

        return self.cleaned_data


class ScheduledReportForm(forms.Form):
    INTERVAL_CHOICES = [("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")]

    config_ids = forms.MultipleChoiceField(
        label=_("Saved report(s)"),
        validators=[MinLengthValidator(1)],
        help_text='Note: not all built-in reports support email delivery, so'
                  ' some of your saved reports may not appear in this list')

    interval = forms.TypedChoiceField(
        label=_('Interval'),
        widget=SelectToggle(choices=INTERVAL_CHOICES, apply_bindings=True),
        choices=INTERVAL_CHOICES)

    day = forms.TypedChoiceField(
        label=_("Day"),
        coerce=int,
        required=False,
        choices=[(i, i) for i in range(0, 32)])

    hour = forms.TypedChoiceField(
        label=_('Time'),
        coerce=int,
        choices=ReportNotification.hour_choices())

    start_date = forms.DateField(
        label=_('Report Start Date'),
        required=False
    )

    send_to_owner = forms.BooleanField(
        label=_('Send to owner'),
        required=False
    )

    attach_excel = forms.BooleanField(
        label=_('Attach Excel Report'),
        required=False
    )

    recipient_emails = MultiEmailField(
        label=_('Other recipients'),
        required=False
    )
    email_subject = forms.CharField(
        required=False,
        help_text='Translated into recipient\'s language if set to "%(default_subject)s".' % {
            'default_subject': DEFAULT_REPORT_NOTIF_SUBJECT,
        },
    )

    language = forms.ChoiceField(
        label=_('Language'),
        required=False,
        choices=[('', '')] + langcodes.get_all_langs_for_select(),
        widget=forms.Select()
    )

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_id = 'id-scheduledReportForm'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.add_layout(
            crispy.Layout(
                crispy.Fieldset(
                    ugettext("Configure Scheduled Report"),
                    'config_ids',
                    'interval',
                    'day',
                    'hour',
                    'start_date',
                    crispy.Field(
                        'email_subject',
                        css_class='input-xlarge',
                    ),
                    crispy.Field(
                        'send_to_owner'
                    ),
                    crispy.Field(
                        'attach_excel'
                    ),
                    'recipient_emails',
                    'language',
                    crispy.HTML(
                        render_to_string('reports/partials/privacy_disclaimer.html')
                    )
                ),
                FormActions(
                    crispy.Submit('submit_btn', 'Submit')
                )
            )
        )

        super(ScheduledReportForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(ScheduledReportForm, self).clean()
        if cleaned_data["interval"] == "daily":
            del cleaned_data["day"]
        _verify_email(cleaned_data)
        return cleaned_data


class EmailReportForm(forms.Form):
    subject = forms.CharField(required=False)
    send_to_owner = forms.BooleanField(required=False)
    attach_excel = forms.BooleanField(required=False)
    recipient_emails = MultiEmailField(required=False)
    notes = forms.CharField(required=False)

    def clean(self):
        cleaned_data = super(EmailReportForm, self).clean()
        _verify_email(cleaned_data)
        return cleaned_data


def _verify_email(cleaned_data):
    if ('recipient_emails' in cleaned_data
        and not (cleaned_data['recipient_emails'] or
                     cleaned_data['send_to_owner'])):
        raise forms.ValidationError("You must specify at least one "
                                    "valid recipient")
