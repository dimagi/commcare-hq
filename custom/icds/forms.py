from django import forms
from django.core.exceptions import ValidationError
from django.forms.widgets import Select
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from corehq.apps.hqwebapp.crispy import HQFormHelper
from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from dateutil import parser

from corehq.apps.app_manager.dbaccessors import (
    get_brief_apps_in_domain,
    get_version_build_id,
)
from corehq.apps.app_manager.exceptions import BuildNotFoundException
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import HQFormHelper
from custom.icds.models import HostedCCZ, HostedCCZLink
from custom.icds.tasks.data_pulls import run_data_pull
from custom.icds_reports.const import CUSTOM_DATA_PULLS


class HostedCCZLinkForm(forms.ModelForm):
    class Meta:
        model = HostedCCZLink
        exclude = ('domain',)

    def __init__(self, domain, *args, **kwargs):
        super(HostedCCZLinkForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        save_button_text = _('Update') if self.instance.pk else _('Create')
        self.helper.layout.append(Submit('save', save_button_text))
        if self.instance.pk:
            del self.fields['password']
        else:
            self.fields['password'].widget = forms.PasswordInput()
        if self.instance.pk:
            self.helper.layout.append(Submit('delete', _('Delete')))
        self.helper.layout = crispy.Fieldset(_("CCZ Hosting Link"), self.helper.layout)
        self.fields['identifier'].widget.attrs.update({'class': 'text-lowercase'})
        self.instance.domain = domain


class HostedCCZForm(forms.Form):
    link_id = forms.ChoiceField(label=ugettext_lazy("Link"), choices=(), required=False)
    app_id = forms.ChoiceField(label=ugettext_lazy("Application"), choices=(), required=True)
    version = forms.IntegerField(label=ugettext_lazy('Version'), required=True, widget=Select(choices=[]))
    profile_id = forms.CharField(label=ugettext_lazy('Application Profile'),
                                 required=False, widget=Select(choices=[]))
    file_name = forms.CharField(label=ugettext_lazy("CCZ File Name"), required=False)
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3, 'cols': 15}))
    status = forms.ChoiceField(label=ugettext_lazy("Status"),
                               choices=(
                                   ('', ugettext_lazy('Select Status')),
                                   (HostedCCZ.PENDING, ugettext_lazy('Pending')),
                                   (HostedCCZ.BUILDING, ugettext_lazy('Building')),
                                   (HostedCCZ.FAILED, ugettext_lazy('Failed')),
                                   (HostedCCZ.COMPLETED, ugettext_lazy('Completed'))),
                               required=False,
                               help_text=ugettext_lazy("Applicable for search only"))

    def __init__(self, request, domain, email, *args, **kwargs):
        self.domain = domain
        self.email = email
        super(HostedCCZForm, self).__init__(*args, **kwargs)
        self.fields['link_id'].choices = self.link_choices()
        self.fields['app_id'].choices = self.app_id_choices()
        self.helper = HQFormHelper()
        if request.GET.get('app_id'):
            self.fields['app_id'].initial = request.GET.get('app_id')
        if request.GET.get('link_id'):
            self.fields['link_id'].initial = request.GET.get('link_id')
        if request.GET.get('status'):
            self.fields['status'].initial = request.GET.get('status')
        self.helper.layout = crispy.Layout(
            crispy.Field('link_id', css_class="hqwebapp-select2", data_bind="value: linkId"),
            crispy.Field('app_id', css_class="hqwebapp-select2", data_bind="value: appId"),
            crispy.Field('version', data_bind="value: version"),
            crispy.Field('profile_id', id="build-profile-id-input", data_bind="value: profileId"),
            crispy.Field('file_name'),
            crispy.Field('note'),
            crispy.Field('status', data_bind="value: status"),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    crispy.Button(
                        'search',
                        ugettext_lazy("Search"),
                        css_class="btn-default",
                        data_bind="click: search"
                    ),
                    crispy.Button(
                        'clear',
                        ugettext_lazy("Clear"),
                        css_class="btn-default",
                        data_bind="click: clear"
                    ),
                    Submit('submit', ugettext_lazy("Create"))
                )
            )
        )

    def clean_link_id(self):
        if not self.cleaned_data.get('link_id'):
            self.add_error('link_id', _("Please select link"))
        return self.cleaned_data.get('link_id')

    def app_id_choices(self):
        choices = [(None, _('Select Application'))]
        for app in get_brief_apps_in_domain(self.domain):
            choices.append((app.id, app.name))
        return choices

    def link_choices(self):
        choices = [(None, _('Select Link'))]
        for link in HostedCCZLink.objects.filter(domain=self.domain):
            choices.append((link.id, link.identifier))
        return choices

    def _version_exists(self):
        return bool(get_version_build_id(self.domain, self.cleaned_data['app_id'],
                                         self.cleaned_data['version']))

    def clean(self):
        if self.cleaned_data.get('app_id') and self.cleaned_data.get('version'):
            try:
                self._version_exists()
            except BuildNotFoundException as e:
                self.add_error('version', e)

    def save(self):
        try:
            HostedCCZ(
                link_id=self.cleaned_data['link_id'], app_id=self.cleaned_data['app_id'],
                version=self.cleaned_data['version'], profile_id=self.cleaned_data['profile_id'],
                file_name=self.cleaned_data['file_name'],
                note=self.cleaned_data['note'],
            ).save(email=self.email)
        except ValidationError as e:
            return False, ','.join(e.messages)
        return True, None


class CustomDataPullForm(forms.Form):
    data_pull = forms.ChoiceField(label=ugettext_lazy("Data Pull"), choices=(
        (pull.slug, pull.name) for pull in CUSTOM_DATA_PULLS.values()
    ))
    month = forms.DateField(required=True, widget=forms.DateInput())
    location_id = forms.CharField(label=ugettext_lazy("Location"), widget=Select(choices=[]), required=False)

    def __init__(self, request, domain, *args, **kwargs):
        self.domain = domain
        super(CustomDataPullForm, self).__init__(*args, **kwargs)
        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Field('data_pull'),
            crispy.Field('month', id="month_select", css_class="date-picker"),
            crispy.Field('location_id', id='location_search_select'),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    Submit('submit', ugettext_lazy("Submit"))
                )
            )
        )

    def clean_month(self):
        month = self.cleaned_data['month']
        if month and month.day != 1:
            self.add_error("month", "Only first of month should be selected")
        month = month.strftime('%Y-%m-%d')
        return month

    def submit(self, domain, email):
        run_data_pull.delay(self.cleaned_data['data_pull'],
                            domain,
                            self.cleaned_data['month'],
                            self.cleaned_data['location_id'],
                            email)


class CustomSMSReportRequestForm(forms.Form):

    date_range = forms.CharField(
        label=_('Select Date Range'),
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'id': 'date_range_selector'}
        ),
        required=True
    )

    start_date = forms.CharField(widget=forms.HiddenInput(
        attrs={'id': 'report_start_date'}
    ), required=True)
    end_date = forms.CharField(widget=forms.HiddenInput(
        attrs={'id': 'report_end_date'}
    ), required=True)

    def __init__(self, *args, **kwargs):
        super(CustomSMSReportRequestForm, self).__init__(*args, **kwargs)
        self.helper = HQFormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = crispy.Layout(
            hqcrispy.Field('date_range'),
            hqcrispy.Field('start_date'),
            hqcrispy.Field('end_date'),
            twbscrispy.StrictButton(
                _('Generate Report'),
                type='submit',
                css_class='btn-primary',
            )
        )

    def clean_start_date(self):
        start_date = self.cleaned_data['start_date']
        try:
            start_date = parser.parse(start_date).date()
        except ValueError:
            raise forms.ValidationError(_("Invalid date"))
        return start_date

    def clean_end_date(self):
        start_date = self.cleaned_data['start_date']
        end_date = self.cleaned_data['end_date']
        try:
            end_date = parser.parse(end_date).date()
        except ValueError:
            raise forms.ValidationError(_("Invalid date"))
        if start_date > end_date:
            raise forms.ValidationError(_("Start date cannot be greater than end date"))
        return end_date
