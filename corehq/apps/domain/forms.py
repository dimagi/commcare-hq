import copy
import logging
from urlparse import urlparse, parse_qs
import dateutil
import re
import io
from PIL import Image
import uuid
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import UNUSABLE_PASSWORD
from corehq import privileges
from corehq.apps.accounting.exceptions import SubscriptionRenewalError
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.sms.phonenumbers_helper import parse_phone_number
import settings

from django import forms
from crispy_forms.bootstrap import FormActions, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from django.core.urlresolvers import reverse

from django.forms.fields import (ChoiceField, CharField, BooleanField,
    ImageField, DecimalField, IntegerField)
from django.forms.widgets import  Select
from django.utils.encoding import smart_str
from django.contrib.auth.forms import PasswordResetForm
from django.utils.safestring import mark_safe
from django_countries.countries import COUNTRIES
from corehq.apps.accounting.models import BillingContactInfo, BillingAccountAdmin, SubscriptionAdjustmentMethod, Subscription, SoftwarePlanEdition
from corehq.apps.app_manager.models import Application, FormBase, ApplicationBase

from corehq.apps.domain.models import (LOGO_ATTACHMENT, LICENSES, DATA_DICT,
    AREA_CHOICES, SUB_AREA_CHOICES, Domain)
from corehq.apps.reminders.models import CaseReminderHandler

from corehq.apps.users.models import WebUser, CommCareUser
from corehq.apps.groups.models import Group
from dimagi.utils.django.email import send_HTML_email
from dimagi.utils.timezones.fields import TimeZoneField
from dimagi.utils.timezones.forms import TimeZoneChoiceField
from django.template.loader import render_to_string
from django.utils.translation import ugettext_noop, ugettext as _
from corehq.apps.style.forms.widgets import BootstrapCheckboxInput, BootstrapDisabledInput

# used to resize uploaded custom logos, aspect ratio is preserved
LOGO_SIZE = (211, 32)

logger = logging.getLogger(__name__)


def tf_choices(true_txt, false_txt):
    return (('false', false_txt), ('true', true_txt))

class SnapshotSettingsMixin(forms.Form):
    project_type = CharField(label=ugettext_noop("Project Category"), required=False,
        help_text=ugettext_noop("e.g. MCH, HIV, etc."))


class ProjectSettingsForm(forms.Form):
    """
    Form for updating a user's project settings
    """
    global_timezone = forms.CharField(
        initial="UTC",
        label="Project Timezone",
        widget=BootstrapDisabledInput(attrs={'class': 'input-xlarge'}))
    override_global_tz = forms.BooleanField(
        initial=False,
        required=False,
        label="",
        widget=BootstrapCheckboxInput(
            attrs={'data-bind': 'checked: override_tz, event: {change: updateForm}'},
            inline_label=ugettext_noop("Override project's timezone setting just for me.")))
    user_timezone = TimeZoneChoiceField(
        label="My Timezone",
        initial=global_timezone.initial,
        widget=forms.Select(attrs={'class': 'input-xlarge', 'bindparent': 'visible: override_tz',
                                   'data-bind': 'event: {change: updateForm}'}))

    def clean_user_timezone(self):
        data = self.cleaned_data['user_timezone']
        timezone_field = TimeZoneField()
        timezone_field.run_validators(data)
        return smart_str(data)

    def save(self, user, domain):
        try:
            timezone = self.cleaned_data['global_timezone']
            override = self.cleaned_data['override_global_tz']
            if override:
                timezone = self.cleaned_data['user_timezone']
            dm = user.get_domain_membership(domain)
            dm.timezone = timezone
            dm.override_global_tz = override
            user.save()
            return True
        except Exception:
            return False


class SnapshotApplicationForm(forms.Form):
    publish = BooleanField(label=ugettext_noop("Publish?"), required=False)
    name = CharField(label=ugettext_noop("Name"), required=True)
    description = CharField(label=ugettext_noop("Description"), required=False, widget=forms.Textarea,
        help_text=ugettext_noop("A detailed technical description of the application"))
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
            'description',
            'deployment_date',
            'phone_model',
            'user_type',
            'attribution_notes'
        ]

class SnapshotSettingsForm(SnapshotSettingsMixin):
    title = CharField(label=ugettext_noop("Title"), required=True, max_length=100)
    project_type = CharField(label=ugettext_noop("Project Category"), required=True,
        help_text=ugettext_noop("e.g. MCH, HIV, etc."))
    license = ChoiceField(label=ugettext_noop("License"), required=True, choices=LICENSES.items(),
        widget=Select(attrs={'class': 'input-xxlarge'}))
    description = CharField(label=ugettext_noop("Long Description"), required=False, widget=forms.Textarea,
        help_text=ugettext_noop("A high-level overview of your project as a whole"))
    short_description = CharField(label=ugettext_noop("Short Description"), required=False,
        widget=forms.Textarea(attrs={'maxlength': 200}),
        help_text=ugettext_noop("A brief description of your project (max. 200 characters)"))
    share_multimedia = BooleanField(label=ugettext_noop("Share all multimedia?"), required=False,
        help_text=ugettext_noop("This will allow any user to see and use all multimedia in this project"))
    share_reminders = BooleanField(label=ugettext_noop("Share Reminders?"), required=False,
        help_text=ugettext_noop("This will publish reminders along with this project"))
    image = forms.ImageField(label=ugettext_noop("Exchange image"), required=False,
        help_text=ugettext_noop("An optional image to show other users your logo or what your app looks like"))
    video = CharField(label=ugettext_noop("Youtube Video"), required=False,
        help_text=ugettext_noop("An optional youtube clip to tell users about your app. Please copy and paste a URL to a youtube video"))
    cda_confirmed = BooleanField(required=False, label=ugettext_noop("Content Distribution Agreement"))

    def __init__(self, *args, **kw):
        super(SnapshotSettingsForm, self).__init__(*args, **kw)
        self.fields.keyOrder = [
            'title',
            'short_description',
            'description',
            'project_type',
            'image',
            'video',
            'share_multimedia',
            'share_reminders',
            'license',
            'cda_confirmed',]
        self.fields['license'].help_text = \
            render_to_string('domain/partials/license_explanations.html', {
                'extra': _("All un-licensed multimedia files in "
                           "your project will be given this license")
            })
        self.fields['cda_confirmed'].help_text = \
            render_to_string('domain/partials/cda_modal.html')

    def clean_cda_confirmed(self):
        data_cda = self.cleaned_data['cda_confirmed']
        data_publish = self.data.get('publish_on_submit', "no") == "yes"
        if data_publish and data_cda is False:
            raise forms.ValidationError('You must agree to our Content Distribution Agreement to publish your project.')
        return data_cda

    def clean_video(self):
        video = self.cleaned_data['video']
        if not video:
            return video

        def video_id(value):
            # http://stackoverflow.com/questions/4356538/how-can-i-extract-video-id-from-youtubes-link-in-python#answer-7936523
            """
            Examples:
            - http://youtu.be/SA2iWivDJiE
            - http://www.youtube.com/watch?v=_oPAwA_Udwc&feature=feedu
            - http://www.youtube.com/embed/SA2iWivDJiE
            - http://www.youtube.com/v/SA2iWivDJiE?version=3&amp;hl=en_US
            """
            query = urlparse(value)
            if query.hostname == 'youtu.be':
                return query.path[1:]
            if query.hostname in ('www.youtube.com', 'youtube.com'):
                if query.path == '/watch':
                    p = parse_qs(query.query)
                    return p['v'][0]
                if query.path[:7] == '/embed/':
                    return query.path.split('/')[2]
                if query.path[:3] == '/v/':
                    return query.path.split('/')[2]
                    # fail?
            return None

        v_id = video_id(video)
        if not v_id:
            raise forms.ValidationError('This is not a correctly formatted youtube URL. Please use a different URL.')
        return v_id

    def clean(self):
        cleaned_data = self.cleaned_data
        sm = cleaned_data["share_multimedia"]
        license = cleaned_data["license"]
        app_ids = self._get_apps_to_publish()

        if sm and license not in self.dom.most_restrictive_licenses(apps_to_check=app_ids):
            license_choices = [LICENSES[l] for l in self.dom.most_restrictive_licenses(apps_to_check=app_ids)]
            msg = render_to_string('domain/partials/restrictive_license.html', {'licenses': license_choices})
            self._errors["license"] = self.error_class([msg])

            del cleaned_data["license"]

        sr = cleaned_data["share_reminders"]
        if sr:  # check that the forms referenced by the events in each reminders exist in the project
            referenced_forms = CaseReminderHandler.get_referenced_forms(domain=self.dom.name)
            if referenced_forms:
                apps = [Application.get(app_id) for app_id in app_ids]
                app_forms = [f.unique_id for forms in [app.get_forms() for app in apps] for f in forms]
                nonexistent_forms = filter(lambda f: f not in app_forms, referenced_forms)
                nonexistent_forms = [FormBase.get_form(f) for f in nonexistent_forms]
                if nonexistent_forms:
                    msg = """
                        Your reminders reference forms that are not being published.
                        Make sure the following forms are being published: %s
                    """ % str([f.default_name() for f in nonexistent_forms]).strip('[]')
                    self._errors["share_reminders"] = self.error_class([msg])

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

class SubAreaMixin():
    def clean_sub_area(self):
        area = self.cleaned_data['area']
        sub_area = self.cleaned_data['sub_area']

        if sub_area:
            if not area:
                raise forms.ValidationError(_('You may not specify a sub area when the project has no specified area'))
        else:
            return None

        sub_areas = []
        for a in DATA_DICT["area"]:
            if a["name"] == area:
                sub_areas = a["sub_areas"]

        if sub_area not in sub_areas:
            raise forms.ValidationError(_('This is not a valid sub-area for the area %s') % area)
        return sub_area

class DomainGlobalSettingsForm(forms.Form):
    default_timezone = TimeZoneChoiceField(label=ugettext_noop("Default Timezone"), initial="UTC")

    logo = ImageField(
        label=_("Custom Logo"),
        required=False,
        help_text=_("Upload a custom image to display instead of the "
                    "CommCare HQ logo.  It will be automatically resized to "
                    "a height of 32 pixels.")
    )
    delete_logo = BooleanField(
        label=_("Delete Logo"),
        required=False,
        help_text=_("Delete your custom logo and use the standard one.")
    )

    def __init__(self, *args, **kwargs):
        self.can_use_custom_logo = kwargs.pop('can_use_custom_logo', False)
        super(DomainGlobalSettingsForm, self).__init__(*args, **kwargs)
        if not self.can_use_custom_logo:
            del self.fields['logo']
            del self.fields['delete_logo']

    def clean_default_timezone(self):
        data = self.cleaned_data['default_timezone']
        timezone_field = TimeZoneField()
        timezone_field.run_validators(data)
        return smart_str(data)

    def save(self, request, domain):
        try:
            if self.can_use_custom_logo:
                logo = self.cleaned_data['logo']
                if logo:

                    input_image = Image.open(io.BytesIO(logo.read()))
                    input_image.load()
                    input_image.thumbnail(LOGO_SIZE)
                    # had issues trying to use a BytesIO instead
                    tmpfilename = "/tmp/%s_%s" % (uuid.uuid4(), logo.name)
                    input_image.save(tmpfilename, 'PNG')

                    with open(tmpfilename) as tmpfile:
                        domain.put_attachment(tmpfile, name=LOGO_ATTACHMENT)
                elif self.cleaned_data['delete_logo']:
                    domain.delete_attachment(LOGO_ATTACHMENT)

            global_tz = self.cleaned_data['default_timezone']
            domain.default_timezone = global_tz
            users = WebUser.by_domain(domain.name)
            for user in users:
                dm = user.get_domain_membership(domain.name)
                if not dm.override_global_tz:
                    dm.timezone = global_tz
                    user.save()
            domain.save()
            return True
        except Exception:
            return False

class DomainMetadataForm(DomainGlobalSettingsForm, SnapshotSettingsMixin):
    customer_type = ChoiceField(
        label=_("Customer Type"),
        choices=(('basic', _('Basic')),
                 ('plus', _('Plus')),
                 ('full', _('Full')))
    )
    is_test = ChoiceField(
        label=_("Test Project"),
        choices=(('true', _('Test')),
                 ('false', _('Real')),
                 ('none', _('Not Sure')))
    )
    commconnect_enabled = BooleanField(
        label=_("CommConnect Enabled"),
        required=False,
        help_text=_("CommConnect is a CommCareHQ module for SMS messages, "
                    "reminders and data collection.")
    )
    survey_management_enabled = BooleanField(
        label=_("Survey Management Enabled"),
        required=False,
        help_text=_("Survey Management is a CommCareHQ module for SMS and "
                    "Call Center based surveys for large samples.  It is "
                    "under active development. Do not enable for your domain "
                    "unless you're piloting it.")
    )
    sms_case_registration_enabled = BooleanField(
        label=_("Enable Case Registration Via SMS"),
        required=False
    )
    sms_case_registration_type = CharField(
        label=_("SMS Case Registration Type"),
        required=False
    )
    sms_case_registration_owner_id = ChoiceField(
        label=_("SMS Case Registration Owner"),
        required=False,
        choices=[]
    )
    sms_case_registration_user_id = ChoiceField(
        label=_("SMS Case Registration Submitting User"),
        required=False,
        choices=[]
    )
    call_center_enabled = BooleanField(
        label=_("Call Center Application"),
        required=False,
        help_text=_("Call Center mode is a CommCareHQ module for managing "
                    "call center workflows. It is still under "
                    "active development. Do not enable for your domain unless "
                    "you're actively piloting it.")
    )
    call_center_case_owner = ChoiceField(
        label=_("Call Center Case Owner"),
        initial=None,
        required=False,
        help_text=_("Select the person who will be listed as the owner "
                    "of all cases created for call center users.")
    )
    call_center_case_type = CharField(
        label=_("Call Center Case Type"),
        required=False,
        help_text=_("Enter the case type to be used for FLWs in call center apps")
    )
    restrict_superusers = BooleanField(
        label=_("Restrict Superuser Access"),
        required=False,
        help_text=_("If access to a domain is restricted only users added " +
                    "to the domain and staff members will have access.")
    )
    ota_restore_caching = BooleanField(
        label=_("Enable Restore Caching (beta)"),
        required=False,
        help_text=_(
            "Speed up phone restores. Useful if you have users with "
            "large case lists and are getting timeouts during restore. "
            "This feature is still in testing. Don't enable unless "
            "you are an advanced user."
        )
    )
    secure_submissions = BooleanField(
        label=_("Only accept secure submissions"),
        required=False,
        help_text=_("Turn this on to prevent others from impersonating your "
                    "mobile workers. To use, all of your deployed applications "
                    "must be using secure submissions."),
    )
    cloudcare_releases = ChoiceField(
        label=_("CloudCare should use"),
        initial=None,
        required=False,
        choices=(
            ('stars', _('Latest starred version')),
            ('nostars', _('Every version (not recommended)')),
        ),
        help_text=_("Choose whether CloudCare should use the latest "
                    "starred build or every build in your application.")
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        domain = kwargs.pop('domain', None)
        super(DomainMetadataForm, self).__init__(*args, **kwargs)

        if not (user and user.is_previewer):
            self.fields['call_center_enabled'].widget = forms.HiddenInput()
            self.fields['call_center_case_owner'].widget = forms.HiddenInput()
            self.fields['call_center_case_type'].widget = forms.HiddenInput()

        if not (user and user.is_staff):
            self.fields['restrict_superusers'].widget = forms.HiddenInput()

        project = Domain.get_by_name(domain)
        if project.cloudcare_releases == 'default' or not domain_has_privilege(domain, privileges.CLOUDCARE):
            # if the cloudcare_releases flag was just defaulted, don't bother showing
            # this setting at all
            self.fields['cloudcare_releases'].widget = forms.HiddenInput()

        if domain is not None:
            groups = Group.get_case_sharing_groups(domain)
            users = CommCareUser.by_domain(domain)

            domain_group_choices = [(group._id, group.name) for group in groups]
            domain_user_choices = [(user._id, user.raw_username) for user in users]
            domain_owner_choices = domain_group_choices + domain_user_choices

            self.fields["sms_case_registration_owner_id"].choices = domain_owner_choices
            self.fields["sms_case_registration_user_id"].choices = domain_user_choices

            call_center_user_choices = [(user._id, user.raw_username + ' [user]')
                                         for user in users]
            call_center_group_choices = [(group._id, group.name + ' [group]')
                                         for group in groups]

            self.fields["call_center_case_owner"].choices = \
                [('', '')] + \
                call_center_user_choices + \
                call_center_group_choices

    def _validate_sms_registration_field(self, field_name, error_msg):
        value = self.cleaned_data.get(field_name)
        if value is not None:
            value = value.strip()
        if self.cleaned_data.get("sms_case_registration_enabled", False):
            if value is None or value == "":
                raise forms.ValidationError(error_msg)
        return value

    def clean_sms_case_registration_type(self):
        return self._validate_sms_registration_field("sms_case_registration_type", _("Please enter a default case type for cases that register themselves via sms."))

    def clean_sms_case_registration_owner_id(self):
        return self._validate_sms_registration_field("sms_case_registration_owner_id", _("Please enter a default owner for cases that register themselves via sms."))

    def clean_sms_case_registration_user_id(self):
        return self._validate_sms_registration_field("sms_case_registration_user_id", _("Please enter a default submitting user for cases that register themselves via sms."))

    def save(self, request, domain):
        res = DomainGlobalSettingsForm.save(self, request, domain)

        if not res:
            return False
        try:
            domain.project_type = self.cleaned_data['project_type']
            domain.customer_type = self.cleaned_data['customer_type']
            domain.is_test = self.cleaned_data['is_test']
            domain.commconnect_enabled = self.cleaned_data.get(
                    'commconnect_enabled', False)
            domain.survey_management_enabled = self.cleaned_data.get('survey_management_enabled', False)
            domain.sms_case_registration_enabled = self.cleaned_data.get('sms_case_registration_enabled', False)
            domain.sms_case_registration_type = self.cleaned_data.get('sms_case_registration_type')
            domain.sms_case_registration_owner_id = self.cleaned_data.get('sms_case_registration_owner_id')
            domain.sms_case_registration_user_id = self.cleaned_data.get('sms_case_registration_user_id')
            domain.call_center_config.enabled = self.cleaned_data.get('call_center_enabled', False)
            if domain.call_center_config.enabled:
                domain.internal.using_call_center = True
                domain.call_center_config.case_owner_id = self.cleaned_data.get('call_center_case_owner', None)
                domain.call_center_config.case_type = self.cleaned_data.get('call_center_case_type', None)
            domain.restrict_superusers = self.cleaned_data.get('restrict_superusers', False)
            domain.ota_restore_caching = self.cleaned_data.get('ota_restore_caching', False)
            cloudcare_releases = self.cleaned_data.get('cloudcare_releases')
            if cloudcare_releases and domain.cloudcare_releases != 'default':
                # you're never allowed to change from default
                domain.cloudcare_releases = cloudcare_releases
            secure_submissions = self.cleaned_data.get('secure_submissions', False)
            apps_to_save = []
            if secure_submissions != domain.secure_submissions:
                for app in ApplicationBase.by_domain(domain.name):
                    if app.secure_submissions != secure_submissions:
                        app.secure_submissions = secure_submissions
                        apps_to_save.append(app)
            domain.secure_submissions = secure_submissions
            domain.save()
            if apps_to_save:
                ApplicationBase.bulk_save(apps_to_save)
            return True
        except Exception, e:
            logging.exception("couldn't save project settings - error is %s" % e)
            return False


class DomainDeploymentForm(forms.Form):
    city = CharField(label=ugettext_noop("City"), required=False)
    country = CharField(label=ugettext_noop("Country"), required=False)
    region = CharField(label=ugettext_noop("Region"), required=False,
        help_text=ugettext_noop("e.g. US, LAC, SA, Sub-Saharan Africa, Southeast Asia, etc."))
    deployment_date = CharField(label=ugettext_noop("Deployment date"), required=False)
    description = CharField(label=ugettext_noop("Description"), required=False, widget=forms.Textarea)
    public = ChoiceField(label=ugettext_noop("Make Public?"), choices=tf_choices('Yes', 'No'), required=False)

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

def tuple_of_copies(a_list, blank=True):
    ret = [(item, item) for item in a_list]
    if blank:
        ret.insert(0, ('', '---'))
    return tuple(ret)

class DomainInternalForm(forms.Form, SubAreaMixin):
    sf_contract_id = CharField(label=ugettext_noop("Salesforce Contract ID"), required=False)
    sf_account_id = CharField(label=ugettext_noop("Salesforce Account ID"), required=False)
    commcare_edition = ChoiceField(label=ugettext_noop("CommCare Plan"), initial="community", required=False,
                                   choices=tuple([(p, p) for p in
                                                  ["community", "standard", "pro", "advanced", "enterprise"]]))
    services = ChoiceField(label=ugettext_noop("Services"), required=False,
                           choices=tuple_of_copies(["basic", "plus", "full", "custom"]))
    initiative = forms.MultipleChoiceField(label=ugettext_noop("Initiative"), widget=forms.CheckboxSelectMultiple(),
                                           choices=tuple_of_copies(DATA_DICT["initiatives"], blank=False), required=False)
    workshop_region = CharField(label=ugettext_noop("Workshop Region"), required=False,
        help_text=ugettext_noop("e.g. US, LAC, SA, Sub-Saharan Africa, Southeast Asia, etc."))
    project_state = ChoiceField(label=ugettext_noop("Project State"), required=False,
                                choices=tuple_of_copies(["POC", "transition", "at-scale"]))
    self_started = ChoiceField(label=ugettext_noop("Self Started?"), choices=tf_choices('Yes', 'No'), required=False)
    area = ChoiceField(label=ugettext_noop("Sector"), required=False, choices=tuple_of_copies(AREA_CHOICES))
    sub_area = ChoiceField(label=ugettext_noop("Sub-Sector"), required=False, choices=tuple_of_copies(SUB_AREA_CHOICES))
    using_adm = ChoiceField(label=ugettext_noop("Using ADM?"), choices=tf_choices('Yes', 'No'), required=False)
    using_call_center = ChoiceField(label=ugettext_noop("Using Call Center?"), choices=tf_choices('Yes', 'No'), required=False)
    custom_eula = ChoiceField(label=ugettext_noop("Custom Eula?"), choices=tf_choices('Yes', 'No'), required=False)
    can_use_data = ChoiceField(label=ugettext_noop("Data Usage?"), choices=tf_choices('Yes', 'No'), required=False)
    organization_name = CharField(label=ugettext_noop("Organization Name"), required=False)
    notes = CharField(label=ugettext_noop("Notes"), required=False, widget=forms.Textarea)
    platform = forms.MultipleChoiceField(label=ugettext_noop("Platform"), widget=forms.CheckboxSelectMultiple(),
                                         choices=tuple_of_copies(["java", "android", "cloudcare"], blank=False), required=False)
    phone_model = CharField(label=ugettext_noop("Phone Model"), required=False)
    project_manager = CharField(label=ugettext_noop("Project Manager's Email"), required=False)
    goal_time_period = IntegerField(label=ugettext_noop("Goal time period (in days)"), required=False)
    goal_followup_rate = DecimalField(label=ugettext_noop("Goal followup rate (percentage in decimal format. e.g. 70% is .7)"), required=False)

    def save(self, domain):
        kw = {"workshop_region": self.cleaned_data["workshop_region"]} if self.cleaned_data["workshop_region"] else {}
        domain.update_internal(sf_contract_id=self.cleaned_data['sf_contract_id'],
            sf_account_id=self.cleaned_data['sf_account_id'],
            commcare_edition=self.cleaned_data['commcare_edition'],
            services=self.cleaned_data['services'],
            initiative=self.cleaned_data['initiative'],
            project_state=self.cleaned_data['project_state'],
            self_started=self.cleaned_data['self_started'] == 'true',
            area=self.cleaned_data['area'],
            sub_area=self.cleaned_data['sub_area'],
            using_adm=self.cleaned_data['using_adm'] == 'true',
            using_call_center=self.cleaned_data['using_call_center'] == 'true',
            custom_eula=self.cleaned_data['custom_eula'] == 'true',
            can_use_data=self.cleaned_data['can_use_data'] == 'true',
            organization_name=self.cleaned_data['organization_name'],
            notes=self.cleaned_data['notes'],
            platform=self.cleaned_data['platform'],
            project_manager=self.cleaned_data['project_manager'],
            phone_model=self.cleaned_data['phone_model'],
            goal_time_period=self.cleaned_data['goal_time_period'],
            goal_followup_rate=self.cleaned_data['goal_followup_rate'],
            **kw
        )




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


class HQPasswordResetForm(PasswordResetForm):
    """
    Modified from PasswordResetForm to filter only web users by default.

    This prevents duplicate emails with linked commcare user accounts to the same email.
    """

    def clean_email(self):
        UserModel = get_user_model()
        email = self.cleaned_data["email"]
        matching_users = UserModel._default_manager.filter(username__iexact=email)
        if matching_users.count():
            self.users_cache = matching_users
        else:
            # revert to previous behavior to theoretically allow commcare users to create an account
            self.users_cache = UserModel._default_manager.filter(email__iexact=email)

        # below here is not modified from the superclass
        if not len(self.users_cache):
            raise forms.ValidationError(self.error_messages['unknown'])
        if not any(user.is_active for user in self.users_cache):
            # none of the filtered users are active
            raise forms.ValidationError(self.error_messages['unknown'])
        if any((user.password == UNUSABLE_PASSWORD)
               for user in self.users_cache):
            raise forms.ValidationError(self.error_messages['unusable'])
        return email


class ConfidentialPasswordResetForm(HQPasswordResetForm):
    def clean_email(self):
        try:
            return super(ConfidentialPasswordResetForm, self).clean_email()
        except forms.ValidationError:
            # The base class throws various emails that give away information about the user;
            # we can pretend all is well since the save() method is safe for missing users.
            return self.cleaned_data['email']


class EditBillingAccountInfoForm(forms.ModelForm):
    billing_admins = forms.CharField(
        required=False,
        label=ugettext_noop("Other Billing Admins"),
        help_text=ugettext_noop(mark_safe(
            "<p>These are the Web Users that will be able to access and "
            "modify your account's subscription and billing information.</p> "
            "<p>Your logged in account is already a Billing Administrator."
            "</p>"
        )),
    )

    class Meta:
        model = BillingContactInfo
        fields = ['first_name', 'last_name', 'phone_number', 'emails', 'company_name', 'first_line',
                  'second_line', 'city', 'state_province_region', 'postal_code', 'country']

    def __init__(self, account, domain, creating_user, data=None, *args, **kwargs):
        self.account = account
        self.domain = domain
        self.creating_user = creating_user

        try:
            self.current_country = self.account.billingcontactinfo.country
        except Exception:
            initial = kwargs.get('initial')
            self.current_country = initial.get('country') if initial is not None else None

        try:
            kwargs['instance'] = self.account.billingcontactinfo
        except BillingContactInfo.DoesNotExist:
            pass

        super(EditBillingAccountInfoForm, self).__init__(data, *args, **kwargs)

        other_admins = self.account.billing_admins.filter(
            domain=self.domain).exclude(web_user=self.creating_user).all()
        self.fields['billing_admins'].initial = ','.join([o.web_user for o in other_admins])

        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Billing Administrators"),
                crispy.Field('billing_admins', css_class='input-xxlarge'),
            ),
            crispy.Fieldset(
                _("Basic Information"),
                'company_name',
                'first_name',
                'last_name',
                crispy.Field('emails', css_class='input-xxlarge'),
                'phone_number',
            ),
            crispy.Fieldset(
                 _("Mailing Address"),
                'first_line',
                'second_line',
                'city',
                'state_province_region',
                'postal_code',
                crispy.Field('country', css_class="input-large",
                             data_countryname=dict(COUNTRIES).get(self.current_country, '')),
            ),
            FormActions(
                StrictButton(
                    _("Update Billing Information"),
                    type="submit",
                    css_class='btn btn-primary',
                ),
            ),
        )

    def clean_billing_admins(self):
        data = self.cleaned_data['billing_admins']
        all_admins = data.split(',')
        result = []
        for admin in all_admins:
            if admin and admin != u'':
                result.append(BillingAccountAdmin.objects.get_or_create(
                    web_user=admin,
                    domain=self.domain,
                )[0])
        result.append(BillingAccountAdmin.objects.get_or_create(
            web_user=self.creating_user,
            domain=self.domain,
        )[0])
        return result

    def clean_phone_number(self):
        data = self.cleaned_data['phone_number']
        parsed_number = None
        if data:
            for country in ["US", "GB", None]:
                parsed_number = parse_phone_number(data, country, failhard=False)
                if parsed_number is not None:
                    break
            if parsed_number is None:
                raise forms.ValidationError(_("It looks like this phone number is invalid. "
                                              "Did you forget the country code?"))
            return "+%s%s" % (parsed_number.country_code, parsed_number.national_number)

    def save(self, commit=True):
        billing_contact_info = super(EditBillingAccountInfoForm, self).save(commit=False)
        billing_contact_info.account = self.account
        billing_contact_info.save()

        billing_admins = self.cleaned_data['billing_admins']
        other_domain_admins = copy.copy(self.account.billing_admins.exclude(
            domain=self.domain).all())
        self.account.billing_admins.clear()
        for other_admin in other_domain_admins:
            self.account.billing_admins.add(other_admin)
        for admin in billing_admins:
            self.account.billing_admins.add(admin)
        self.account.save()
        return True


class ConfirmNewSubscriptionForm(EditBillingAccountInfoForm):
    plan_edition = forms.CharField(
        widget=forms.HiddenInput,
    )

    def __init__(self, account, domain, creating_user, plan_version, current_subscription, data=None, *args, **kwargs):
        self.plan_version = plan_version
        self.current_subscription = current_subscription
        super(ConfirmNewSubscriptionForm, self).__init__(account, domain, creating_user, data=data, *args, **kwargs)

        self.fields['plan_edition'].initial = self.plan_version.plan.edition

        from corehq.apps.domain.views import DomainSubscriptionView
        self.helper.layout = crispy.Layout(
            'plan_edition',
            crispy.Fieldset(
                _("Billing Administrators"),
                crispy.Field('billing_admins', css_class='input-xxlarge'),
            ),
            crispy.Fieldset(
                _("Basic Information"),
                'company_name',
                'first_name',
                'last_name',
                crispy.Field('emails', css_class='input-xxlarge'),
                'phone_number',
            ),
            crispy.Fieldset(
                 _("Mailing Address"),
                'first_line',
                'second_line',
                'city',
                'state_province_region',
                'postal_code',
                crispy.Field('country', css_class="input-large",
                             data_countryname=dict(COUNTRIES).get(self.current_country, ''))
            ),
            FormActions(
                crispy.HTML('<a href="%(url)s" style="margin-right:5px;" class="btn">%(title)s</a>' % {
                    'url': reverse(DomainSubscriptionView.urlname, args=[self.domain]),
                    'title': _("Cancel"),
                }),
                StrictButton(
                    _("Subscribe to Plan"),
                    type="submit",
                    css_class='btn btn-success',
                ),
            ),
        )

    def save(self, commit=True):
        account_save_success = super(ConfirmNewSubscriptionForm, self).save(commit=False)
        if not account_save_success:
            return False

        try:
            if self.current_subscription is not None:
                if self.plan_version.plan.edition == SoftwarePlanEdition.COMMUNITY:
                    self.current_subscription.cancel_subscription(adjustment_method=SubscriptionAdjustmentMethod.USER,
                                                                  web_user=self.creating_user)
                else:
                    subscription = self.current_subscription.change_plan(
                        self.plan_version, web_user=self.creating_user, adjustment_method=SubscriptionAdjustmentMethod.USER
                    )
                    subscription.is_active = True
                    subscription.save()
            else:
                subscription = Subscription.new_domain_subscription(
                    self.account, self.domain, self.plan_version,
                    web_user=self.creating_user,
                    adjustment_method=SubscriptionAdjustmentMethod.USER)
                subscription.is_active = True
                if subscription.plan_version.plan.edition == SoftwarePlanEdition.ENTERPRISE:
                    # this point can only be reached if the initiating user was a superuser
                    subscription.do_not_invoice = True
                subscription.save()
            return True
        except Exception:
            logger.exception("There was an error subscribing the domain '%s' to plan '%s'. "
                             "Go quickly!" % (self.domain, self.plan_version.plan.name))
        return False


class ConfirmSubscriptionRenewalForm(EditBillingAccountInfoForm):
    plan_edition = forms.CharField(
        widget=forms.HiddenInput,
    )
    confirm_legal = forms.BooleanField(
        required=True,
    )

    def __init__(self, account, domain, creating_user, current_subscription,
                 renewed_version, data=None, *args, **kwargs):
        self.current_subscription = current_subscription
        super(ConfirmSubscriptionRenewalForm, self).__init__(
            account, domain, creating_user, data=data, *args, **kwargs
        )

        self.fields['plan_edition'].initial = renewed_version.plan.edition
        self.fields['confirm_legal'].label = mark_safe(ugettext_noop(
            'I have read and agree to the <a href="%(pa_url)s" '
            'target="_blank">Software Product Agreement</a>.'
        ) % {
            'pa_url': reverse("product_agreement"),
        })

        from corehq.apps.domain.views import DomainSubscriptionView
        self.helper.layout = crispy.Layout(
            'plan_edition',
            crispy.Fieldset(
                _("Billing Administrators"),
                crispy.Field('billing_admins', css_class='input-xxlarge'),
            ),
            crispy.Fieldset(
                _("Basic Information"),
                'company_name',
                'first_name',
                'last_name',
                crispy.Field('emails', css_class='input-xxlarge'),
                'phone_number',
            ),
            crispy.Fieldset(
                 _("Mailing Address"),
                'first_line',
                'second_line',
                'city',
                'state_province_region',
                'postal_code',
                crispy.Field('country', css_class="input-large",
                             data_countryname=dict(COUNTRIES).get(self.current_country, ''))
            ),
            crispy.Fieldset(
                _("Re-Confirm Product Agreement"),
                'confirm_legal',
            ),
            FormActions(
                crispy.HTML('<a href="%(url)s" style="margin-right:5px;" class="btn">%(title)s</a>' % {
                    'url': reverse(DomainSubscriptionView.urlname, args=[self.domain]),
                    'title': _("Cancel"),
                }),
                StrictButton(
                    _("Renew Plan"),
                    type="submit",
                    css_class='btn btn-success',
                ),
            ),
        )

    def save(self, commit=True):
        account_save_success = super(ConfirmSubscriptionRenewalForm, self).save(commit=False)
        if not account_save_success:
            return False

        try:
            self.current_subscription.renew_subscription(
                web_user=self.creating_user,
                adjustment_method=SubscriptionAdjustmentMethod.USER,
            )
        except SubscriptionRenewalError as e:
            logger.error("[BILLING] Subscription for %(domain)s failed to "
                         "renew due to: %(error)s." % {
                             'domain': self.domain,
                             'error': e,
                         })
        return True


class ProBonoForm(forms.Form):
    contact_email = forms.CharField(label=_("Contact email"))
    organization = forms.CharField(label=_("Organization"))
    project_overview = forms.CharField(widget=forms.Textarea, label="Project overview")
    pay_only_features_needed = forms.CharField(widget=forms.Textarea, label="Pay only features needed")
    duration_of_project = forms.CharField(help_text=_(
        "We grant pro-bono subscriptions to match the duration of your "
        "project, up to a maximum of 12 months at a time (at which point "
        "you need to reapply)."
    ))
    domain = forms.CharField(label=_("Project Space"))
    dimagi_contact = forms.CharField(
        help_text=_("If you have already been in touch with someone from "
                    "Dimagi, please list their name."),
        required=False)
    num_expected_users = forms.CharField(label=_("Number of expected users"))

    def __init__(self, use_domain_field, *args, **kwargs):
        super(ProBonoForm, self).__init__(*args, **kwargs)
        if not use_domain_field:
            self.fields['domain'].required = False
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
            _('Pro-Bono Application'),
                'contact_email',
                'organization',
                crispy.Div(
                    'domain',
                    style=('' if use_domain_field else 'display:none'),
                ),
                'project_overview',
                'pay_only_features_needed',
                'duration_of_project',
                'num_expected_users',
                'dimagi_contact',
            ),
            FormActions(
                crispy.ButtonHolder(
                    crispy.Submit('submit_pro_bono', _('Submit Pro-Bono Application'))
                )
            ),
        )

    def process_submission(self, domain=None):
        try:
            params = {
                'pro_bono_form': self,
                'domain': domain,
            }
            html_content = render_to_string("domain/email/pro_bono_application.html", params)
            text_content = render_to_string("domain/email/pro_bono_application.txt", params)
            recipient = settings.BILLING_EMAIL
            subject = "[Pro-Bono Application]"
            if domain is not None:
                subject = "%s %s" % (subject, domain)
            send_HTML_email(subject, recipient, html_content, text_content=text_content,
                            email_from=settings.DEFAULT_FROM_EMAIL)
        except Exception:
            logging.error("Couldn't send pro-bono application email. "
                          "Contact: %s" % self.cleaned_data['contact_email']
            )
