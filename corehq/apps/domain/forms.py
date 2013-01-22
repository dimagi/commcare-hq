import dateutil
import re
from django import forms

from django.forms.fields import ChoiceField, CharField, BooleanField
from django.forms.widgets import  Select
from django.utils.encoding import smart_str

from corehq.apps.domain.models import LICENSES

from corehq.apps.users.models import WebUser
from dimagi.utils.timezones.fields import TimeZoneField
from dimagi.utils.timezones.forms import TimeZoneChoiceField
from django.template.loader import render_to_string
from django.utils.translation import ugettext_noop

import corehq.apps.commtrack.util as commtrack_util

class SnapshotSettingsMixin(forms.Form):
    project_type = CharField(label=ugettext_noop("Project Category"), required=False,
        help_text=ugettext_noop("e.g. MCH, HIV, etc."))

class SnapshotApplicationForm(forms.Form):
    publish = BooleanField(label=ugettext_noop("Publish?"), required=False)
    name = CharField(label=ugettext_noop("Name"), required=True)
    short_description = CharField(label=ugettext_noop("Short Description"), required=False,
        max_length=200, widget=forms.Textarea,
        help_text=ugettext_noop("A brief description of the application (max. 200 characters)"))
    description = CharField(label=ugettext_noop("Long Description"), required=False, widget=forms.Textarea,
        help_text=ugettext_noop("A detailed technical description of the app design"))
    deployment_date = CharField(label=ugettext_noop("Deployment date"), required=False)
    phone_model = CharField(label=ugettext_noop("Phone model"), required=False)
    user_type = CharField(label=ugettext_noop("User type"), required=False,
        help_text=ugettext_noop("e.g. CHW, ASHA, RA, etc"))
    attribution_notes = CharField(label=ugettext_noop("Attribution notes"), required=False,
        help_text=ugettext_noop("Enter any special instructions to users here. This will be shown just before users copy your project."), widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super(SnapshotApplicationForm, self).__init__(*args, **kwargs)
        self.fields.keyOrder = [
            'publish',
            'name',
            'short_description',
            'description',
            'deployment_date',
            'phone_model',
            'user_type',
            'attribution_notes'
        ]

class SnapshotSettingsForm(SnapshotSettingsMixin):
    title = CharField(label=ugettext_noop("Title"), required=True)
    author = CharField(label=ugettext_noop("Author name"), required=True)
    project_type = CharField(label=ugettext_noop("Project Category"), required=True,
        help_text=ugettext_noop("e.g. MCH, HIV, etc."))
    license = ChoiceField(label=ugettext_noop("License"), required=True, choices=LICENSES.items(),
        widget=Select(attrs={'class': 'input-xxlarge'}),
        help_text=render_to_string('domain/partials/license_explanations.html',
            {'extra': ugettext_noop("All un-licensed multimedia files in your project will be given this license")}))
    description = CharField(label=ugettext_noop("Long Description"), required=False, widget=forms.Textarea,
        help_text=ugettext_noop("A high-level overview of your project as a whole"))
    short_description = CharField(label=ugettext_noop("Short Description"), required=False,
        max_length=200, widget=forms.Textarea,
        help_text=ugettext_noop("A brief description of your project (max. 200 characters)"))
    share_multimedia = BooleanField(label=ugettext_noop("Share all multimedia?"), required=False,
        help_text=ugettext_noop("This will allow any user to see and use all multimedia in this project"))
    image = forms.ImageField(label=ugettext_noop("Exchange image"), required=False,
        help_text=ugettext_noop("An optional image to show other users your logo or what your app looks like"))
    cda_confirmed = BooleanField(required=False, label=ugettext_noop("Content Distribution Agreement"),
        help_text=render_to_string('domain/partials/cda_modal.html'))
    publish_on_submit = BooleanField(required=False, label=ugettext_noop("Immediately publish?"),
        help_text=ugettext_noop("If this is selected, the project will be published when you submit this form"))

    def __init__(self, *args, **kw):
        super(SnapshotSettingsForm, self).__init__(*args, **kw)
        self.fields.keyOrder = [
            'title',
            'author',
            'short_description',
            'description',
            'project_type',
            'image',
            'share_multimedia',
            'license',
            'publish_on_submit',
            'cda_confirmed',]

    def clean_cda_confirmed(self):
        data_cda = self.cleaned_data['cda_confirmed']
        data_publish = self.cleaned_data['publish_on_submit']
        if data_publish is True and data_cda is False:
            raise forms.ValidationError('You must agree to our Content Distribution Agreement to publish your project.')
        return data_cda

    def clean(self):
        cleaned_data = self.cleaned_data
        sm = cleaned_data["share_multimedia"]
        license = cleaned_data["license"]
        apps = self._get_apps_to_publish()

        if sm and license not in self.dom.most_restrictive_licenses(apps_to_check=apps):
            license_choices = [LICENSES[l] for l in self.dom.most_restrictive_licenses(apps_to_check=apps)]
            msg = render_to_string('domain/partials/restrictive_license.html', {'licenses': license_choices})
            self._errors["license"] = self.error_class([msg])

            del cleaned_data["license"]

        return cleaned_data

    def _get_apps_to_publish(self):
        app_ids = []
        for d, val in self.data.iteritems():
            d = d.split('-')
            if len(d) < 2:
                continue
            if d[1] == 'publish' and val == 'on':
                app_ids.append(d[0])

        return app_ids

########################################################################################################

class DomainGlobalSettingsForm(forms.Form):
    default_timezone = TimeZoneChoiceField(label=ugettext_noop("Default Timezone"), initial="UTC")
    case_sharing = ChoiceField(label=ugettext_noop("Case Sharing"), choices=(('false', 'Off'), ('true', 'On')))

    def clean_default_timezone(self):
        data = self.cleaned_data['default_timezone']
        timezone_field = TimeZoneField()
        timezone_field.run_validators(data)
        return smart_str(data)

    def save(self, request, domain):
        try:
            global_tz = self.cleaned_data['default_timezone']
            domain.default_timezone = global_tz
            users = WebUser.by_domain(domain.name)
            for user in users:
                dm = user.get_domain_membership(domain.name)
                if not dm.override_global_tz:
                    dm.timezone = global_tz
                    user.save()
            domain.case_sharing = self.cleaned_data['case_sharing'] == 'true'
            domain.save()
            return True
        except Exception:
            return False

class DomainMetadataForm(DomainGlobalSettingsForm, SnapshotSettingsMixin):
    customer_type = ChoiceField(label='Customer Type',
        choices=(('basic', 'Basic'), ('plus', 'Plus'), ('full', 'Full')))
    is_test = ChoiceField(label='Test Project', choices=(('false', 'Real'), ('true', 'Test')))
    survey_management_enabled = BooleanField(label='Survey Management Enabled', required=False)
    commtrack_enabled = BooleanField(label='CommTrack Enabled', required=False, help_text='CommTrack is a CommCareHQ module for logistics, inventory tracking, and supply chain management. It is still under active development. Do not enable for your domain unless you\'re actively piloting it.')

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(DomainMetadataForm, self).__init__(*args, **kwargs)
        if not (user and user.is_previewer):
            # commtrack is pre-release
            self.fields['commtrack_enabled'].widget = forms.HiddenInput()

    def save(self, request, domain):
        res = DomainGlobalSettingsForm.save(self, request, domain)
        if not res:
            return False
        try:
            domain.project_type = self.cleaned_data['project_type']
            domain.customer_type = self.cleaned_data['customer_type']
            domain.is_test = self.cleaned_data['is_test'] == 'true'
            domain.survey_management_enabled = self.cleaned_data.get('survey_management_enabled', False)
            domain.commtrack_enabled = self.cleaned_data.get('commtrack_enabled', False)
            if domain.commtrack_enabled and not domain.commtrack_settings:
                commtrack_util.bootstrap_default(domain.name)
            domain.save()
            return True
        except Exception:
            return False

class DomainDeploymentForm(forms.Form):
    city = CharField(label=ugettext_noop("City"), required=False)
    country = CharField(label=ugettext_noop("Country"), required=False)
    region = CharField(label=ugettext_noop("Region"), required=False,
        help_text=ugettext_noop("e.g. US, LAC, SA, Sub-Saharan Africa, Southeast Asia, etc."))
    deployment_date = CharField(label=ugettext_noop("Deployment date"), required=False)
    description = CharField(label=ugettext_noop("Description"), required=False, widget=forms.Textarea)
    public = ChoiceField(label=ugettext_noop("Make Public?"), choices=(('false', 'No'), ('true', 'Yes')), required=False)

    def save(self, domain):
        try:
            domain.update_deployment(city=self.cleaned_data['city'],
                country=self.cleaned_data['country'],
                region=self.cleaned_data['region'],
                date=dateutil.parser.parse(self.cleaned_data['deployment_date']),
                description=self.cleaned_data['description'],
                public=(self.cleaned_data['public'] == 'true'))
            return True
        except Exception:
            return False


########################################################################################################

min_pwd = 4
max_pwd = 20
pwd_pattern = re.compile( r"([-\w]){"  + str(min_pwd) + ',' + str(max_pwd) + '}' )

def clean_password(txt):
    if len(txt) < min_pwd:
        raise forms.ValidationError('Password is too short; must be at least %s characters' % min_pwd )
    if len(txt) > max_pwd:
        raise forms.ValidationError('Password is too long; must be less than %s characters' % max_pwd )
    if not pwd_pattern.match(txt):
        raise forms.ValidationError('Password may only contain letters, numbers, hyphens, and underscores')
    return txt
