from django import forms
from django.core.validators import MinLengthValidator
from django.template.loader import render_to_string
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from memoized import memoized

from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from crispy_forms.bootstrap import StrictButton

import langcodes
from corehq.apps.hqwebapp.crispy import FormActions, HQFormHelper, LinkButton
from corehq.apps.hqwebapp.fields import MultiEmailField
from corehq.apps.hqwebapp.widgets import SelectToggle
from corehq.apps.reports.models import TableauServer, TableauVisualization
from corehq.apps.saved_reports.models import (
    DEFAULT_REPORT_NOTIF_SUBJECT,
    ReportConfig,
    ReportNotification,
)
from corehq.apps.userreports.reports.view import ConfigurableReportView
from corehq.toggles import HOURLY_SCHEDULED_REPORT, NAMESPACE_DOMAIN


class SavedReportConfigForm(forms.Form):
    name = forms.CharField()
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
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
    INTERVAL_CHOICES = [
        ("daily", _("Daily")),
        ("weekly", _("Weekly")),
        ("monthly", _("Monthly"))
    ]

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

    stop_hour = forms.TypedChoiceField(
        label=_('To Time'),
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
        super(ScheduledReportForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_id = 'id-scheduledReportForm'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        domain = kwargs.get('initial', {}).get('domain', None)
        if domain is not None and HOURLY_SCHEDULED_REPORT.enabled(domain, NAMESPACE_DOMAIN):
            self.fields['interval'].choices.insert(0, ("hourly", gettext("Hourly")))
            self.fields['interval'].widget.choices.insert(0, ("hourly", gettext("Hourly")))

        self.helper.add_layout(
            crispy.Layout(
                crispy.Fieldset(
                    gettext("Configure Scheduled Report"),
                    'config_ids',
                    'interval',
                    'day',
                    'hour',
                    'stop_hour',
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

    def clean(self):
        cleaned_data = super(ScheduledReportForm, self).clean()
        if cleaned_data.get("interval") == "daily":
            del cleaned_data["day"]
        if cleaned_data.get("interval") == "hourly":
            del cleaned_data["day"]
        _verify_email(cleaned_data)
        return cleaned_data

    def clean_stop_hour(self):
        cleaned_data = super(ScheduledReportForm, self).clean()
        if cleaned_data.get("interval") == "hourly":
            if cleaned_data['hour'] > cleaned_data['stop_hour']:
                self.add_error('stop_hour', _("Must be after 'From Time'"))

        return cleaned_data.get('stop_hour')


class EmailReportForm(forms.Form):
    subject = forms.CharField(required=False, label=_('Subject'))
    send_to_owner = forms.BooleanField(required=False, label=_('Send to me'))
    recipient_emails = MultiEmailField(required=False, label=_('Additional Recipients'))
    notes = forms.CharField(required=False, label=_('Report notes'), widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = HQFormHelper()
        self.helper.field_class = "col-xs-10"
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field('subject', data_bind="value: subject"),
                crispy.Field('send_to_owner', data_bind="checked: send_to_owner"),
                crispy.Field('recipient_emails', css_id='email-report-recipient_emails',
                    data_bind="selectedOptions: recipient_emails"),
                crispy.Field('notes', data_bind="value: notes"),
                css_class='modal-body'
            ),
            FormActions(
                crispy.Div(
                    crispy.Button('close', _('Close'), css_class='btn btn-default cancel-button',
                        data_bind='click: resetModal', data_dismiss='modal'),
                    crispy.Submit('submit_btn', _('Send Email'), css_class="btn btn-primary send-button",
                        data_bind='click: sendEmail', data_loading_text=_('Sending...')),
                    css_class='pull-right',
                )
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        _verify_email(cleaned_data)
        return cleaned_data

    def get_readable_errors(self):
        errors = []

        if not self.errors:
            return errors

        for field in self.errors:
            field_name = self.fields[field].label if field in self.fields else ''
            for error in self.errors.get_json_data(escape_html=True)[field]:
                prefix = f'{field_name}: ' if field_name else ''
                errors.append(f'{prefix}{error["message"]}')

        return errors


def _verify_email(cleaned_data):
    if ('recipient_emails' in cleaned_data
        and not (cleaned_data['recipient_emails']
            or cleaned_data['send_to_owner'])):
        raise forms.ValidationError("You must specify at least one "
                                    "valid recipient")


class TableauServerForm(forms.Form):

    server_type = forms.CharField(
        label=_('Server Type'),
        widget=forms.Select(choices=[
            ("", _("Select server type")),
            ('server', _('Tableau Server')),
            ('online', _('Tableau Online')),
        ]),
    )

    server_name = forms.CharField(
        label=_('Server Name')
    )

    validate_hostname = forms.CharField(
        label=_('Validate Hostname'),
        required=False,
    )

    target_site = forms.CharField(
        label=_('Target Site'),
    )

    tableau_groups_allowed = forms.MultipleChoiceField(
        label=_("Allowed Tableau Groups"),
        choices=[],
        required=False,
        widget=forms.CheckboxSelectMultiple()
    )

    class Meta:
        model = TableauServer
        fields = [
            'server_type',
            'server_name',
            'validate_hostname',
            'target_site',
            'tableau_groups_allowed'
        ]

    def __init__(self, data, user_syncing_config={}, *args, **kwargs):
        self.domain = kwargs.pop('domain')
        kwargs['initial'] = self.initial_data
        super(TableauServerForm, self).__init__(data, *args, **kwargs)
        self.fields['tableau_groups_allowed'].choices = []

        self.helper = HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field('server_type'),
            ),
            crispy.Div(
                crispy.Field('server_name'),
            ),
            crispy.Div(
                crispy.Field('validate_hostname'),
            ),
            crispy.Div(
                crispy.Field('target_site'),
            ),
            FormActions(
                crispy.Submit('submit_btn', 'Submit')
            )
        )

        if user_syncing_config['user_syncing_enabled'] and user_syncing_config.get('server_reachable'):
            self._setup_tableau_groups_allowed_field(kwargs, user_syncing_config)
            self.add_allowed_tableau_groups_field = bool(self.fields['tableau_groups_allowed'].choices)
            if self.add_allowed_tableau_groups_field:
                self.helper.layout.insert(
                    -1,
                    'tableau_groups_allowed',
                )
        else:
            self.add_allowed_tableau_groups_field = False

    def _setup_tableau_groups_allowed_field(self, kwargs, user_syncing_config):
        self.all_tableau_groups = user_syncing_config['all_tableau_groups']
        allowed_tableau_groups_initial = kwargs['initial']['allowed_tableau_groups']
        self.fields['tableau_groups_allowed'].initial = []
        for i, group in enumerate(self.all_tableau_groups):
            self.fields['tableau_groups_allowed'].choices.append((i, group.name))
            if allowed_tableau_groups_initial and group.name in allowed_tableau_groups_initial:
                self.fields['tableau_groups_allowed'].initial.append(i)

    @property
    @memoized
    def _existing_config(self):
        existing, _created = TableauServer.objects.get_or_create(
            domain=self.domain
        )
        return existing

    @property
    def initial_data(self):
        return {
            'server_type': self._existing_config.server_type,
            'server_name': self._existing_config.server_name,
            'validate_hostname': self._existing_config.validate_hostname,
            'target_site': self._existing_config.target_site,
            'allowed_tableau_groups': self._existing_config.allowed_tableau_groups,
        }

    def save(self):
        self._existing_config.server_type = self.cleaned_data['server_type']
        self._existing_config.server_name = self.cleaned_data['server_name']
        self._existing_config.validate_hostname = self.cleaned_data['validate_hostname']
        self._existing_config.target_site = self.cleaned_data['target_site']
        if self.add_allowed_tableau_groups_field:
            self._existing_config.allowed_tableau_groups = [
                self.all_tableau_groups[int(i)].name for i in self.cleaned_data['tableau_groups_allowed']]
        self._existing_config.save()


class TableauVisualizationForm(forms.ModelForm):
    view_url = forms.CharField(
        label=_('View URL'),
    )

    class Meta:
        model = TableauVisualization
        fields = [
            'title',
            'server',
            'view_url',
        ]

    def __init__(self, domain, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = domain
        self.fields['server'].queryset = TableauServer.objects.filter(domain=domain)

    @property
    def helper(self):
        helper = HQFormHelper()
        from corehq.apps.reports.views import TableauVisualizationListView
        helper.layout = crispy.Layout(
            crispy.Field('title'),
            crispy.Field('server'),
            crispy.Field('view_url'),

            FormActions(
                StrictButton(
                    _("Save"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
                LinkButton(
                    _("Cancel"),
                    reverse(
                        TableauVisualizationListView.urlname,
                        kwargs={'domain': self.domain},
                    ),
                    css_class="btn btn-default",
                ),
            ),
        )
        return helper

    def save(self, commit=True):
        self.instance.domain = self.domain
        return super().save(commit)


class UpdateTableauVisualizationForm(TableauVisualizationForm):
    id = forms.CharField(widget=forms.HiddenInput())

    class Meta:
        model = TableauVisualization
        fields = [
            'id',
            'title',
            'server',
            'view_url',
        ]

    @property
    def helper(self):
        helper = HQFormHelper()
        helper.form_style = 'default'
        helper.form_show_labels = True
        helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field('id'),
                crispy.Field('title'),
                crispy.Field('server'),
                crispy.Field('view_url'),
                css_class='modal-body',
            ),
            FormActions(
                StrictButton(
                    _("Update"),
                    css_class='btn btn-primary',
                    type='submit',
                ),
                crispy.Button(
                    'cancel',
                    _("Cancel"),
                    css_class="btn btn-default",
                    data_dismiss="modal",
                ),
                css_class='modal-footer',
            ),
        )
        return helper
