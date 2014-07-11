from django import forms
from django.core.validators import MinLengthValidator
from corehq.apps.style.forms.fields import MultiEmailField
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from .models import ReportNotification


class ScheduledReportForm(forms.Form):
    config_ids = forms.MultipleChoiceField(
        label="Saved report(s)",
        validators=[MinLengthValidator(1)],
        help_text='Note: not all built-in reports support email delivery, so'
                  ' some of your saved reports may not appear in this list')

    interval = forms.TypedChoiceField(
        label='Interval',
        choices=[("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")])

    day = forms.TypedChoiceField(
        label="Day",
        coerce=int,
        required=False,
        choices=[(i, i) for i in range(0, 32)])

    timezone_source = forms.TypedChoiceField(
        label='Timezone source',
        choices=[("domain", "Domain"), ("user", "User")])

    hour = forms.TypedChoiceField(
        label='Time',
        coerce=int,
        choices=ReportNotification.hour_choices())

    send_to_owner = forms.BooleanField(
        label='Send to me',
        required=False)

    attach_excel = forms.BooleanField(
        label='Attach Excel Report',
        required=False)

    recipient_emails = MultiEmailField(
        label='Other recipients',
        required=False)

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.add_input(Submit('submit', 'Submit'))

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