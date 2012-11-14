from django import forms
from django.core.validators import MinLengthValidator
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from .models import ReportConfig, ReportNotification
from corehq.apps.users.models import WebUser
from corehq.apps.hqwebapp.fields import MultiEmailField

class attrdict(dict):

    def __getattr__(self, name):
        return self[name]

def make_scheduled_report_form(domain, user_id, instance=None):
    configs = ReportConfig.by_domain_and_owner(domain, user_id).all()
    config_choices = [(c._id, c.full_name) for c in configs
                      if c.report.emailable]

    if not config_choices:
        return lambda *args, **kwargs: None

    web_users = WebUser.view('users/web_users_by_domain', reduce=False,
                               key=domain, include_docs=True).all()
    web_user_emails = [u.get_email() for u in web_users]

    instance = instance or attrdict(
        config_ids=[],
        day_of_week=-1,
        hours=8,
        send_to_owner=True,
        recipient_emails=''
    )

    class ScheduledReportForm(forms.Form):

        config_ids = forms.MultipleChoiceField(
            label="Saved report(s)",
            initial=instance.config_ids,
            choices=config_choices,
            validators=[MinLengthValidator(1)],
            help_text='You can use Ctrl-Click to select multiple items.<br/>Note:'
                      ' not all built-in reports support email delivery, so'
                      ' some of your saved reports may not appear in this list')

        day_of_week = forms.TypedChoiceField(
            label='Day',
            initial=instance.day_of_week,
            coerce=int,
            choices=(('Daily',
                         ((-1, 'Every Day'),)),
                     ('Once a week on...',
                         ReportNotification.day_choices())))

        hours = forms.TypedChoiceField(
            label='Time',
            initial=instance.hours,
            coerce=int,
            choices=ReportNotification.hour_choices(),
            help_text='Sorry, at the moment all times are in GMT.')

        send_to_owner = forms.BooleanField(
            label='Send to me',
            initial=instance.send_to_owner,
            required=False)

        recipient_emails = MultiEmailField(
            label='Other recipients',
            initial=instance.recipient_emails,
            choices=web_user_emails,
            required=False)

        def __init__(self, *args, **kwargs):
            self.helper = FormHelper()
            self.helper.form_class = 'form-horizontal'
            self.helper.add_input(Submit('submit', 'Submit'))

            super(ScheduledReportForm, self).__init__(*args, **kwargs)

        def clean(self):
            cleaned_data = super(ScheduledReportForm, self).clean()
            
            if ('recipient_emails' in cleaned_data
                and not (cleaned_data['recipient_emails'] or
                         cleaned_data['send_to_owner'])):
                raise forms.ValidationError("You must specify at least one "
                        "valid recipient")

            return cleaned_data

    return ScheduledReportForm
