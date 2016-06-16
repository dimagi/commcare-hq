import datetime
import io
import logging
import re
import sys
import uuid
from urlparse import urlparse, parse_qs

import dateutil
from captcha.fields import CaptchaField
from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from dateutil.relativedelta import relativedelta
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.models import get_current_site
from django.core.urlresolvers import reverse
from django.db import transaction
from django.forms.fields import (ChoiceField, CharField, BooleanField,
    ImageField, IntegerField)
from django.forms.widgets import  Select
from django.template.loader import render_to_string
from django.utils.encoding import smart_str, force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_noop, ugettext as _, ugettext_lazy
from django_countries.data import COUNTRIES
from PIL import Image
from pyzxcvbn import zxcvbn

from corehq import privileges
from corehq.apps.accounting.models import (
    BillingAccount,
    BillingAccountType,
    BillingContactInfo,
    CreditAdjustmentReason,
    CreditLine,
    Currency,
    DefaultProductPlan,
    FeatureType,
    PreOrPostPay,
    ProBonoStatus,
    SoftwarePlanEdition,
    SoftwarePlanVersion,
    Subscription,
    SubscriptionAdjustment,
    SubscriptionAdjustmentMethod,
    SubscriptionAdjustmentReason,
    SubscriptionType,
    EntryPoint,
    FundingSource
)
from corehq.apps.accounting.exceptions import SubscriptionRenewalError
from corehq.apps.accounting.utils import (
    domain_has_privilege,
    get_privileges,
    log_accounting_error,
)
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.models import Application, FormBase, RemoteApp
from corehq.apps.domain.models import (LOGO_ATTACHMENT, LICENSES, DATA_DICT,
    AREA_CHOICES, SUB_AREA_CHOICES, BUSINESS_UNITS, TransferDomainRequest)
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.tasks import send_mail_async, send_html_email_async
from corehq.apps.reminders.models import CaseReminderHandler
from corehq.apps.sms.phonenumbers_helper import parse_phone_number
from corehq.apps.style import crispy as hqcrispy
from corehq.apps.style.forms.widgets import BootstrapCheckboxInput
from corehq.apps.users.models import WebUser, CommCareUser, CouchUser
from corehq.privileges import (
    REPORT_BUILDER_5,
    REPORT_BUILDER_ADD_ON_PRIVS,
    REPORT_BUILDER_TRIAL,
)
from corehq.toggles import CALL_CENTER_LOCATION_OWNERS, HIPAA_COMPLIANCE_CHECKBOX
from corehq.util.timezones.fields import TimeZoneField
from corehq.util.timezones.forms import TimeZoneChoiceField
from dimagi.utils.decorators.memoized import memoized

# used to resize uploaded custom logos, aspect ratio is preserved
LOGO_SIZE = (211, 32)

logger = logging.getLogger(__name__)


def tf_choices(true_txt, false_txt):
    return (('false', false_txt), ('true', true_txt))


class ProjectSettingsForm(forms.Form):
    """
    Form for updating a user's project settings
    """
    global_timezone = forms.CharField(
        initial="UTC",
        label="Project Timezone",
        widget=forms.HiddenInput
    )
    override_global_tz = forms.BooleanField(
        initial=False,
        required=False,
        label="",
        widget=BootstrapCheckboxInput(
            inline_label=ugettext_noop("Override project's timezone setting just for me.")
        )
    )
    user_timezone = TimeZoneChoiceField(
        label="My Timezone",
        initial=global_timezone.initial
    )

    def __init__(self, *args, **kwargs):
        super(ProjectSettingsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_id = 'my-project-settings-form'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.all().wrap_together(crispy.Fieldset, 'Override Project Timezone')
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Override Project Timezone',
                crispy.Field('global_timezone', css_class='input-xlarge'),
                twbscrispy.PrependedText(
                    'override_global_tz', '', data_bind='checked: override_tz, event: {change: updateForm}'
                ),
                crispy.Div(
                    crispy.Field(
                        'user_timezone',
                        css_class='input-xlarge',
                        data_bind='event: {change: updateForm}'
                    ),
                    data_bind='visible: override_tz'
                )
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _("Update My Settings"),
                    type="submit",
                    css_id="update-proj-settings",
                    css_class='btn-primary disabled',
                    data_bind="hqbSubmitReady: form_is_ready"
                )
            )
        )

    def clean_user_timezone(self):
        data = self.cleaned_data['user_timezone']
        timezone_field = TimeZoneField()
        timezone_field.run_validators(data)
        return smart_str(data)

    def save(self, user, domain):
        timezone = self.cleaned_data['global_timezone']
        override = self.cleaned_data['override_global_tz']
        if override:
            timezone = self.cleaned_data['user_timezone']
        dm = user.get_domain_membership(domain)
        dm.timezone = timezone
        dm.override_global_tz = override
        user.save()
        return True


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
        help_text=ugettext_noop(
            "Enter any special instructions to users here. "
            "This will be shown just before users copy your project."),
        widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super(SnapshotApplicationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            twbscrispy.PrependedText('publish', ''),
            crispy.Div(
                'name',
                'description',
                'deployment_date',
                'phone_model',
                'user_type',
                'attribution_notes'
            )
        )


class SnapshotFixtureForm(forms.Form):
    publish = BooleanField(label=ugettext_noop("Publish?"), required=False)
    description = CharField(label=ugettext_noop("Description"), required=False, widget=forms.Textarea,
        help_text=ugettext_noop("A detailed technical description of the table"))

    def __init__(self, *args, **kwargs):
        super(SnapshotFixtureForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            twbscrispy.PrependedText('publish', ''),
            'description',
        )


class SnapshotSettingsForm(forms.Form):
    title = CharField(label=ugettext_noop("Title"), required=True, max_length=100)
    project_type = CharField(
        label=ugettext_noop("Project Category"),
        required=True,
        help_text=ugettext_noop("e.g. MCH, HIV, etc.")
    )
    license = ChoiceField(label=ugettext_noop("License"), required=True, choices=LICENSES.items(),
                          widget=Select(attrs={'class': 'input-xxlarge'}))
    description = CharField(
        label=ugettext_noop("Long Description"), required=False, widget=forms.Textarea,
        help_text=ugettext_noop("A high-level overview of your project as a whole"))
    short_description = CharField(
        label=ugettext_noop("Short Description"), required=False,
        widget=forms.Textarea(attrs={'maxlength': 200}),
        help_text=ugettext_noop("A brief description of your project (max. 200 characters)"))
    share_multimedia = BooleanField(label=ugettext_noop("Share all multimedia?"), required=False,
        help_text=ugettext_noop("This will allow any user to see and use all multimedia in this project"))
    share_reminders = BooleanField(label=ugettext_noop("Share Reminders?"), required=False,
        help_text=ugettext_noop("This will publish reminders along with this project"))
    image = forms.ImageField(label=ugettext_noop("Exchange image"), required=False,
        help_text=ugettext_noop("An optional image to show other users your logo or what your app looks like"))
    old_image = forms.BooleanField(required=False)

    video = CharField(label=ugettext_noop("Youtube Video"), required=False,
        help_text=ugettext_noop("An optional youtube clip to tell users about your app. Please copy and paste a URL to a youtube video"))
    documentation_file = forms.FileField(label=ugettext_noop("Documentation File"), required=False,
        help_text=ugettext_noop("An optional file to tell users more about your app."))
    old_documentation_file = forms.BooleanField(required=False)
    cda_confirmed = BooleanField(required=False, label=ugettext_noop("Content Distribution Agreement"))
    is_starter_app = BooleanField(required=False, label=ugettext_noop("This is a starter application"))

    def __init__(self, *args, **kw):
        self.dom = kw.pop("domain", None)
        self.is_superuser = kw.pop("is_superuser", None)
        super(SnapshotSettingsForm, self).__init__(*args, **kw)

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Project Description',
                'title',
                'short_description',
                'description',
                'project_type',
                'image',
                crispy.Field(
                    'old_image',
                    template='domain/partials/old_snapshot_image.html'
                )
            ),
            crispy.Fieldset(
                'Documentation',
                'video',
                'documentation_file',
                crispy.Field(
                    'old_documentation_file',
                    template='domain/partials/old_snapshot_documentation_file.html'
                )
            ),
            crispy.Fieldset(
                'Content',
                twbscrispy.PrependedText('share_multimedia', ''),
                twbscrispy.PrependedText('share_reminders', '')
            ),
            crispy.Fieldset(
                'Licensing',
                'license',
                twbscrispy.PrependedText('cda_confirmed', ''),
            ),
        )

        if self.is_superuser:
            self.helper.layout.append(
                crispy.Fieldset('Starter App', twbscrispy.PrependedText('is_starter_app', ''))
            )

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


class TransferDomainFormErrors(object):
    USER_DNE = ugettext_lazy(u'The user being transferred to does not exist')
    DOMAIN_MISMATCH = ugettext_lazy(u'Mismatch in domains when confirming')


class TransferDomainForm(forms.ModelForm):

    class Meta:
        model = TransferDomainRequest
        fields = ['domain', 'to_username']

    def __init__(self, domain, from_username, *args, **kwargs):
        super(TransferDomainForm, self).__init__(*args, **kwargs)
        self.current_domain = domain
        self.from_username = from_username

        self.fields['domain'].label = _(u'Type the name of the project to confirm')
        self.fields['to_username'].label = _(u'New owner\'s CommCare username')

        self.helper = FormHelper()
        self.helper.layout = crispy.Layout(
            'domain',
            'to_username',
            StrictButton(
                _("Transfer Project"),
                type="submit",
                css_class='btn-danger',
            )
        )

    def save(self, commit=True):
        instance = super(TransferDomainForm, self).save(commit=False)
        instance.from_username = self.from_username
        if commit:
            instance.save()
        return instance

    def clean_domain(self):
        domain = self.cleaned_data['domain']

        if domain != self.current_domain:
            raise forms.ValidationError(TransferDomainFormErrors.DOMAIN_MISMATCH)

        return domain

    def clean_to_username(self):
        username = self.cleaned_data['to_username']

        if not WebUser.get_by_username(username):
            raise forms.ValidationError(TransferDomainFormErrors.USER_DNE)

        return username


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
    USE_LOCATION_CHOICE = "user_location"
    USE_PARENT_LOCATION_CHOICE = 'user_parent_location'
    LOCATION_CHOICES = [USE_LOCATION_CHOICE, USE_PARENT_LOCATION_CHOICE]
    CASES_AND_FIXTURES_CHOICE = "cases_and_fixtures"
    CASES_ONLY_CHOICE = "cases_only"

    hr_name = forms.CharField(
        label=ugettext_lazy("Project Name"),
        help_text=ugettext_lazy("This name will appear in the upper right corner "
                                "when you are in this project. Changing this name "
                                "will not change the URL of the project.")
    )
    default_timezone = TimeZoneChoiceField(label=ugettext_noop("Default Timezone"), initial="UTC")

    logo = ImageField(
        label=ugettext_lazy("Custom Logo"),
        required=False,
        help_text=ugettext_lazy("Upload a custom image to display instead of the "
                    "CommCare HQ logo.  It will be automatically resized to "
                    "a height of 32 pixels.")
    )
    delete_logo = BooleanField(
        label=ugettext_lazy("Delete Logo"),
        required=False,
        help_text=ugettext_lazy("Delete your custom logo and use the standard one.")
    )
    call_center_enabled = BooleanField(
        label=ugettext_lazy("Call Center Application"),
        required=False,
        help_text=ugettext_lazy("Call Center mode is a CommCareHQ module for managing "
                    "call center workflows. It is still under "
                    "active development. Do not enable for your domain unless "
                    "you're actively piloting it.")
    )
    call_center_type = ChoiceField(
        label=ugettext_lazy("Call Center Type"),
        initial=CASES_AND_FIXTURES_CHOICE,
        choices=[
            (CASES_AND_FIXTURES_CHOICE, "Create cases and indicators"),
            (CASES_ONLY_CHOICE, "Create just cases"),
        ],
        help_text=ugettext_lazy(
            """
            If "Create cases and indicators" is selected, each user will have a case associated with it,
            and fixtures will be synced containing indicators about each user. If "Create just cases"
            is selected, the fixtures will not be created.
            """
        ),
        required=False,
    )
    call_center_case_owner = ChoiceField(
        label=ugettext_lazy("Call Center Case Owner"),
        initial=None,
        required=False,
        help_text=ugettext_lazy("Select the person who will be listed as the owner "
                    "of all cases created for call center users.")
    )
    call_center_case_type = CharField(
        label=ugettext_lazy("Call Center Case Type"),
        required=False,
        help_text=ugettext_lazy("Enter the case type to be used for FLWs in call center apps")
    )

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('domain', None)
        self.domain = self.project.name
        self.can_use_custom_logo = kwargs.pop('can_use_custom_logo', False)
        super(DomainGlobalSettingsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper[3] = twbscrispy.PrependedText('delete_logo', '')
        self.helper[4] = twbscrispy.PrependedText('call_center_enabled', '')
        self.helper.all().wrap_together(crispy.Fieldset, 'Edit Basic Information')
        self.helper.layout.append(
            hqcrispy.FormActions(
                StrictButton(
                    _("Update Basic Info"),
                    type="submit",
                    css_class='btn-primary',
                )
            )
        )

        if not self.can_use_custom_logo:
            del self.fields['logo']
            del self.fields['delete_logo']

        if self.project:
            if not self.project.call_center_config.enabled:
                del self.fields['call_center_enabled']
                del self.fields['call_center_type']
                del self.fields['call_center_case_owner']
                del self.fields['call_center_case_type']
            else:
                groups = Group.get_case_sharing_groups(self.domain)
                users = CommCareUser.by_domain(self.domain)

                call_center_user_choices = [
                    (user._id, user.raw_username + ' [user]') for user in users
                ]
                call_center_group_choices = [
                    (group._id, group.name + ' [group]') for group in groups
                ]
                call_center_location_choices = []
                if CALL_CENTER_LOCATION_OWNERS.enabled(self.domain):
                    call_center_location_choices = [
                        (self.USE_LOCATION_CHOICE, ugettext_lazy("user's location [location]")),
                        (self.USE_PARENT_LOCATION_CHOICE, ugettext_lazy("user's location's parent [location]")),
                    ]

                self.fields["call_center_case_owner"].choices = \
                    [('', '')] + \
                    call_center_location_choices + \
                    call_center_user_choices + \
                    call_center_group_choices

    def clean_default_timezone(self):
        data = self.cleaned_data['default_timezone']
        timezone_field = TimeZoneField()
        timezone_field.run_validators(data)
        return smart_str(data)

    def clean(self):
        cleaned_data = super(DomainGlobalSettingsForm, self).clean()
        if (cleaned_data.get('call_center_enabled') and
                (not cleaned_data.get('call_center_case_type') or
                 not cleaned_data.get('call_center_case_owner') or
                 not cleaned_data.get('call_center_type'))):
            raise forms.ValidationError(_(
                'You must choose a Call Center Type, Owner, and Case Type to use the call center application. '
                'Please uncheck the "Call Center Application" setting or enter values for the other fields.'
            ))

        return cleaned_data

    def _save_logo_configuration(self, domain):
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

    def _save_call_center_configuration(self, domain):
        cc_config = domain.call_center_config
        cc_config.enabled = self.cleaned_data.get('call_center_enabled', False)
        if cc_config.enabled:

            domain.internal.using_call_center = True
            cc_config.use_fixtures = self.cleaned_data['call_center_type'] == self.CASES_AND_FIXTURES_CHOICE

            owner = self.cleaned_data.get('call_center_case_owner', None)
            if owner in self.LOCATION_CHOICES:
                cc_config.call_center_case_owner = None
                cc_config.use_user_location_as_owner = True
                cc_config.user_location_ancestor_level = 1 if owner == self.USE_PARENT_LOCATION_CHOICE else 0
            else:
                cc_config.case_owner_id = owner
                cc_config.use_user_location_as_owner = False

            cc_config.case_type = self.cleaned_data.get('call_center_case_type', None)

    def _save_timezone_configuration(self, domain):
        global_tz = self.cleaned_data['default_timezone']
        if domain.default_timezone != global_tz:
            domain.default_timezone = global_tz
            users = WebUser.by_domain(domain.name)
            users_to_save = []
            for user in users:
                dm = user.get_domain_membership(domain.name)
                if not dm.override_global_tz and dm.timezone != global_tz:
                    dm.timezone = global_tz
                    users_to_save.append(user)
            if users_to_save:
                WebUser.bulk_save(users_to_save)

    def save(self, request, domain):
        domain.hr_name = self.cleaned_data['hr_name']
        self._save_logo_configuration(domain)
        self._save_call_center_configuration(domain)
        self._save_timezone_configuration(domain)
        domain.save()
        return True


class DomainMetadataForm(DomainGlobalSettingsForm):

    cloudcare_releases = ChoiceField(
        label=ugettext_lazy("CloudCare should use"),
        initial=None,
        required=False,
        choices=(
            ('stars', ugettext_lazy('Latest starred version')),
            ('nostars', ugettext_lazy('Highest numbered version (not recommended)')),
        ),
        help_text=ugettext_lazy("Choose whether CloudCare should use the latest "
                    "starred build or highest numbered build in your "
                    "application.")
    )

    def __init__(self, *args, **kwargs):
        super(DomainMetadataForm, self).__init__(*args, **kwargs)

        if self.project.cloudcare_releases == 'default' or not domain_has_privilege(self.domain, privileges.CLOUDCARE):
            # if the cloudcare_releases flag was just defaulted, don't bother showing
            # this setting at all
            del self.fields['cloudcare_releases']

    def save(self, request, domain):
        res = DomainGlobalSettingsForm.save(self, request, domain)

        if not res:
            return False
        try:
            cloudcare_releases = self.cleaned_data.get('cloudcare_releases')
            if cloudcare_releases and domain.cloudcare_releases != 'default':
                # you're never allowed to change from default
                domain.cloudcare_releases = cloudcare_releases
            domain.save()
            return True
        except Exception, e:
            logging.exception("couldn't save project settings - error is %s" % e)
            return False


def tuple_of_copies(a_list, blank=True):
    ret = [(item, item) for item in a_list]
    if blank:
        ret.insert(0, ('', '---'))
    return tuple(ret)


class PrivacySecurityForm(forms.Form):
    restrict_superusers = BooleanField(
        label=ugettext_lazy("Restrict Dimagi Staff Access"),
        required=False,
        help_text=ugettext_lazy("Dimagi staff sometimes require access to projects to provide support. " + 
                                "Checking this box may restrict your ability to receive this support in the event " +
                                "you report an issue. You may also miss out on important communications and updates.")
    )
    secure_submissions = BooleanField(
        label=ugettext_lazy("Secure submissions"),
        required=False,
        help_text=ugettext_lazy(mark_safe(
            "Secure Submissions prevents others from impersonating your mobile workers."
            "This setting requires all deployed applications to be using secure "
            "submissions as well. "
            "<a href='https://help.commcarehq.org/display/commcarepublic/Project+Space+Settings'>"
            "Read more about secure submissions here</a>"))
    )
    secure_sessions = BooleanField(
        label=ugettext_lazy("Shorten Inactivity Timeout"),
        required=False,
        help_text=ugettext_lazy("All web users on this project will be logged out after 30 minutes of inactivity")
    )
    allow_domain_requests = BooleanField(
        label=ugettext_lazy("Web user requests"),
        required=False,
        help_text=ugettext_lazy("Allow unknown users to request web access to the domain."),
    )
    hipaa_compliant = BooleanField(
        label=ugettext_lazy("HIPAA compliant"),
        required=False,
    )
    two_factor_auth = BooleanField(
        label=ugettext_lazy("Two Factor Authentication"),
        required=False,
        help_text=ugettext_lazy("All web users on this project will be required to enable two factor authentication")
    )

    def __init__(self, *args, **kwargs):
        user_name = kwargs.pop('user_name')
        domain = kwargs.pop('domain')
        super(PrivacySecurityForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper[0] = twbscrispy.PrependedText('restrict_superusers', '')
        self.helper[1] = twbscrispy.PrependedText('secure_submissions', '')
        self.helper[2] = twbscrispy.PrependedText('secure_sessions', '')
        self.helper[3] = twbscrispy.PrependedText('allow_domain_requests', '')
        self.helper[4] = twbscrispy.PrependedText('hipaa_compliant', '')
        self.helper[5] = twbscrispy.PrependedText('two_factor_auth', '')
        if not domain_has_privilege(domain, privileges.ADVANCED_DOMAIN_SECURITY):
            self.helper.layout.pop(5)
        if not HIPAA_COMPLIANCE_CHECKBOX.enabled(user_name):
            self.helper.layout.pop(4)
        if not domain_has_privilege(domain, privileges.ADVANCED_DOMAIN_SECURITY):
            self.helper.layout.pop(2)
        self.helper.all().wrap_together(crispy.Fieldset, 'Edit Privacy Settings')
        self.helper.layout.append(
            hqcrispy.FormActions(
                StrictButton(
                    _("Update Privacy Settings"),
                    type="submit",
                    css_class='btn-primary',
                )
            )
        )

    def save(self, domain):
        domain.restrict_superusers = self.cleaned_data.get('restrict_superusers', False)
        domain.allow_domain_requests = self.cleaned_data.get('allow_domain_requests', False)
        domain.secure_sessions = self.cleaned_data.get('secure_sessions', False)
        domain.two_factor_auth = self.cleaned_data.get('two_factor_auth', False)
        secure_submissions = self.cleaned_data.get(
            'secure_submissions', False)
        apps_to_save = []
        if secure_submissions != domain.secure_submissions:
            for app in get_apps_in_domain(domain.name):
                if app.secure_submissions != secure_submissions:
                    app.secure_submissions = secure_submissions
                    apps_to_save.append(app)
        domain.secure_submissions = secure_submissions
        domain.hipaa_compliant = self.cleaned_data.get('hipaa_compliant', False)

        domain.save()

        if apps_to_save:
            apps = [app for app in apps_to_save if isinstance(app, Application)]
            remote_apps = [app for app in apps_to_save if isinstance(app, RemoteApp)]
            if apps:
                Application.bulk_save(apps)
            if remote_apps:
                RemoteApp.bulk_save(remote_apps)

        return True


class DomainInternalForm(forms.Form, SubAreaMixin):
    sf_contract_id = CharField(label=ugettext_noop("Salesforce Contract ID"), required=False)
    sf_account_id = CharField(label=ugettext_noop("Salesforce Account ID"), required=False)
    services = ChoiceField(label=ugettext_noop("Services"), required=False,
                           choices=tuple_of_copies(["basic", "plus", "full", "custom"]))
    initiative = forms.MultipleChoiceField(label=ugettext_noop("Initiative"),
                                           widget=forms.CheckboxSelectMultiple(),
                                           choices=tuple_of_copies(DATA_DICT["initiatives"], blank=False),
                                           required=False)
    workshop_region = CharField(
        label=ugettext_noop("Workshop Region"),
        required=False,
        help_text=ugettext_noop("e.g. US, LAC, SA, Sub-Saharan Africa, Southeast Asia, etc."))
    self_started = ChoiceField(
        label=ugettext_noop("Self Started?"),
        choices=tf_choices('Yes', 'No'),
        required=False,
        help_text=ugettext_noop(
            "The organization built and deployed their app themselves. Dimagi may have provided indirect support"
        ))
    is_test = ChoiceField(
        label=ugettext_lazy("Real Project"),
        choices=(('none', ugettext_lazy('Unknown')),
                 ('true', ugettext_lazy('Test')),
                 ('false', ugettext_lazy('Real')),)
    )
    area = ChoiceField(
        label=ugettext_noop("Sector*"),
        required=False,
        choices=tuple_of_copies(AREA_CHOICES))
    sub_area = ChoiceField(
        label=ugettext_noop("Sub-Sector*"),
        required=False,
        choices=tuple_of_copies(SUB_AREA_CHOICES))
    organization_name = CharField(
        label=ugettext_noop("Organization Name*"),
        required=False,
        help_text=ugettext_lazy("Quick 1-2 sentence summary of the project."),
    )
    notes = CharField(label=ugettext_noop("Notes*"), required=False, widget=forms.Textarea)
    phone_model = CharField(
        label=ugettext_noop("Device Model"),
        help_text=ugettext_lazy("Add CloudCare, if this project is using CloudCare as well"),
        required=False,
    )
    deployment_date = CharField(
        label=ugettext_noop("Deployment date"),
        required=False,
        help_text=ugettext_lazy("Date that the project went live (usually right after training).")
    )
    business_unit = forms.ChoiceField(
        label=ugettext_noop('Business Unit'),
        choices=tuple_of_copies(BUSINESS_UNITS),
        required=False,
    )
    countries = forms.MultipleChoiceField(
        label=ugettext_noop("Countries"),
        choices=sorted(COUNTRIES.items(), key=lambda x: x[0]),
        required=False,
    )
    commtrack_domain = ChoiceField(
        label=ugettext_noop("CommCare Supply Project"),
        choices=tf_choices('Yes', 'No'),
        required=False,
        help_text=ugettext_lazy("This app aims to improve the supply of goods and materials")
    )
    performance_threshold = IntegerField(
        label=ugettext_noop("Performance Threshold"),
        required=False,
        help_text=ugettext_lazy(
            'The number of forms submitted per month for a user to count as "performing well". '
            'The default value is 15.'
        )
    )

    def __init__(self, can_edit_eula, *args, **kwargs):
        super(DomainInternalForm, self).__init__(*args, **kwargs)
        self.can_edit_eula = can_edit_eula
        additional_fields = []
        if self.can_edit_eula:
            additional_fields = ['custom_eula', 'can_use_data']
            self.fields['custom_eula'] = ChoiceField(
                label=ugettext_noop("Custom Eula?"),
                choices=tf_choices(_('Yes'), _('No')),
                required=False,
                help_text='Set to "yes" if this project has a customized EULA as per their contract.'
            )
            self.fields['can_use_data'] = ChoiceField(
                label=ugettext_noop("Can use project data?"),
                choices=tf_choices('Yes', 'No'),
                required=False,
                help_text='Set to "no" if this project opts out of data usage. Defaults to "yes".'
            )

        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Basic Information"),
                'initiative',
                'workshop_region',
                'self_started',
                'is_test',
                'area',
                'sub_area',
                'organization_name',
                'notes',
                'phone_model',
                'deployment_date',
                'business_unit',
                'countries',
                'commtrack_domain',
                'performance_threshold',
                crispy.Div(*additional_fields),
            ),
            crispy.Fieldset(
                _("Salesforce Details"),
                'sf_contract_id',
                'sf_account_id',
                'services',
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _("Update Project Information"),
                    type="submit",
                    css_class='btn-primary',
                ),
            ),
        )

    def save(self, domain):
        kwargs = {"workshop_region": self.cleaned_data["workshop_region"]} if self.cleaned_data["workshop_region"] else {}
        if self.can_edit_eula:
            kwargs['custom_eula'] = self.cleaned_data['custom_eula'] == 'true'
            kwargs['can_use_data'] = self.cleaned_data['can_use_data'] == 'true'

        domain.update_deployment(
            date=dateutil.parser.parse(self.cleaned_data['deployment_date']),
            countries=self.cleaned_data['countries'],
        )
        domain.is_test = self.cleaned_data['is_test']
        domain.update_internal(
            sf_contract_id=self.cleaned_data['sf_contract_id'],
            sf_account_id=self.cleaned_data['sf_account_id'],
            services=self.cleaned_data['services'],
            initiative=self.cleaned_data['initiative'],
            self_started=self.cleaned_data['self_started'] == 'true',
            area=self.cleaned_data['area'],
            sub_area=self.cleaned_data['sub_area'],
            organization_name=self.cleaned_data['organization_name'],
            notes=self.cleaned_data['notes'],
            phone_model=self.cleaned_data['phone_model'],
            commtrack_domain=self.cleaned_data['commtrack_domain'] == 'true',
            performance_threshold=self.cleaned_data['performance_threshold'],
            business_unit=self.cleaned_data['business_unit'],
            **kwargs
        )


########################################################################################################

min_pwd = 4
max_pwd = 20
pwd_pattern = re.compile( r"([-\w]){"  + str(min_pwd) + ',' + str(max_pwd) + '}' )


def clean_password(txt):
    if settings.ENABLE_DRACONIAN_SECURITY_FEATURES:
        strength = legacy_get_password_strength(txt)
        message = _('Password is not strong enough. Requirements: 1 special character, '
                    '1 number, 1 capital letter, minimum length of 8 characters.')
    else:
        # TODO: waiting on upstream PR to fix TypeError https://github.com/taxpon/pyzxcvbn/pull/1
        # until then, we are using a dimagi hosted fork
        strength = zxcvbn(txt, user_inputs=['commcare', 'hq', 'dimagi', 'commcarehq'])
        message = _('Password is not strong enough. Try making your password more complex.')
    if strength['score'] < 2:
        raise forms.ValidationError(message)
    return txt


def legacy_get_password_strength(value):
    # 1 Special Character, 1 Number, 1 Capital Letter with the length of Minimum 8
    # initial score rigged to reach 2 when all requirementss are met
    score = -2
    if SPECIAL.search(value):
        score += 1
    if NUMBER.search(value):
        score += 1
    if UPPERCASE.search(value):
        score += 1
    if len(value) >= 8:
        score += 1
    return {"score": score}


def _get_uppercase_unicode_regexp():
    # rather than add another dependency (regex library)
    # http://stackoverflow.com/a/17065040/10840
    uppers = [u'[']
    for i in xrange(sys.maxunicode):
        c = unichr(i)
        if c.isupper():
            uppers.append(c)
    uppers.append(u']')
    upper_group = u"".join(uppers)
    return re.compile(upper_group, re.UNICODE)

SPECIAL = re.compile(ur"\W", re.UNICODE)
NUMBER = re.compile(ur"\d", re.UNICODE)  # are there other unicode numerals?
UPPERCASE = _get_uppercase_unicode_regexp()


class NoAutocompleteMixin(object):

    def __init__(self, *args, **kwargs):
        super(NoAutocompleteMixin, self).__init__(*args, **kwargs)
        if settings.ENABLE_DRACONIAN_SECURITY_FEATURES:
            for field in self.fields.values():
                field.widget.attrs.update({'autocomplete': 'off'})


class HQPasswordResetForm(NoAutocompleteMixin, forms.Form):
    """
    Only finds users and emails forms where the USERNAME is equal to the
    email specified (preventing Mobile Workers from using this form to submit).

    This small change is why we can't use the default PasswordReset form.
    """
    email = forms.EmailField(label=ugettext_lazy("Username"), max_length=254,
                             widget=forms.TextInput(attrs={'class': 'form-control'}))
    if settings.ENABLE_DRACONIAN_SECURITY_FEATURES:
        captcha = CaptchaField(label=ugettext_lazy("Type the letters in the box"))
    error_messages = {
        'unknown': ugettext_lazy("That email address doesn't have an associated "
                     "user account. Are you sure you've registered?"),
        'unusable': ugettext_lazy("The user account associated with this email "
                       "address cannot reset the password."),
    }

    def clean_email(self):
        UserModel = get_user_model()
        email = self.cleaned_data["email"]
        matching_users = UserModel._default_manager.filter(username__iexact=email)

        # below here is not modified from the superclass
        if not len(matching_users):
            raise forms.ValidationError(self.error_messages['unknown'])
        if not any(user.is_active for user in matching_users):
            # none of the filtered users are active
            raise forms.ValidationError(self.error_messages['unknown'])
        if any((user.password == UNUSABLE_PASSWORD_PREFIX)
               for user in matching_users):
            raise forms.ValidationError(self.error_messages['unusable'])
        return email

    def save(self, domain_override=None,
             subject_template_name='registration/password_reset_subject.txt',
             email_template_name='registration/password_reset_email.html',
             # WARNING: Django 1.7 passes this in automatically. do not remove
             html_email_template_name=None,
             use_https=False, token_generator=default_token_generator,
             from_email=None, request=None):
        """
        Generates a one-use only link for resetting password and sends to the
        user.
        """
        UserModel = get_user_model()
        email = self.cleaned_data["email"]

        # this is the line that we couldn't easily override in PasswordForm where
        # we specifically filter for the username, not the email, so that
        # mobile workers who have the same email set as a web worker don't
        # get a password reset email.
        active_users = UserModel._default_manager.filter(
            username__iexact=email, is_active=True)

        # the code below is copied from default PasswordForm
        for user in active_users:
            # Make sure that no email is sent to a user that actually has
            # a password marked as unusable
            if not user.has_usable_password():
                continue
            if not domain_override:
                current_site = get_current_site(request)
                site_name = current_site.name
                domain = current_site.domain
            else:
                site_name = domain = domain_override
            c = {
                'email': user.email,
                'domain': domain,
                'site_name': site_name,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'user': user,
                'token': token_generator.make_token(user),
                'protocol': 'https' if use_https else 'http',
            }
            subject = render_to_string(subject_template_name, c)
            # Email subject *must not* contain newlines
            subject = ''.join(subject.splitlines())
            email = render_to_string(email_template_name, c)
            send_mail_async.delay(subject, email, from_email, [user.email])


class ConfidentialPasswordResetForm(HQPasswordResetForm):

    def clean_email(self):
        try:
            return super(ConfidentialPasswordResetForm, self).clean_email()
        except forms.ValidationError:
            # The base class throws various emails that give away information about the user;
            # we can pretend all is well since the save() method is safe for missing users.
            return self.cleaned_data['email']


class HQSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(label=ugettext_lazy("New password"),
                                    widget=forms.PasswordInput(
                                        attrs={'data-bind': "value: password, valueUpdate: 'input'"}),
                                    help_text=mark_safe("""
                                    <span data-bind="text: passwordHelp, css: color">
                                    """))

    def clean_new_password1(self):
        return clean_password(self.cleaned_data.get('new_password1'))

    def save(self, commit=True):
        user = super(HQSetPasswordForm, self).save(commit)
        couch_user = CouchUser.from_django_user(user)
        couch_user.last_password_set = datetime.datetime.utcnow()
        if commit:
            couch_user.save()
        return user


class EditBillingAccountInfoForm(forms.ModelForm):

    email_list = forms.CharField(
        label=BillingContactInfo._meta.get_field('email_list').verbose_name,
        help_text=BillingContactInfo._meta.get_field('email_list').help_text,
    )

    class Meta:
        model = BillingContactInfo
        fields = ['first_name', 'last_name', 'phone_number', 'company_name', 'first_line',
                  'second_line', 'city', 'state_province_region', 'postal_code', 'country']

    def __init__(self, account, domain, creating_user, data=None, *args, **kwargs):
        self.account = account
        self.domain = domain
        self.creating_user = creating_user
        is_ops_user = kwargs.pop('is_ops_user', False)

        try:
            self.current_country = self.account.billingcontactinfo.country
        except Exception:
            initial = kwargs.get('initial')
            self.current_country = initial.get('country') if initial is not None else None

        try:
            kwargs['instance'] = self.account.billingcontactinfo
            kwargs['initial'] = {
                'email_list': ','.join(self.account.billingcontactinfo.email_list),
            }

        except BillingContactInfo.DoesNotExist:
            pass

        super(EditBillingAccountInfoForm, self).__init__(data, *args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        fields = [
            'company_name',
            'first_name',
            'last_name',
            crispy.Field('email_list', css_class='input-xxlarge'),
            'phone_number'
        ]

        if is_ops_user and self.initial.get('email_list'):
            fields.insert(4, crispy.Div(
                crispy.Div(
                    css_class='col-sm-3 col-md-2'
                ),
                crispy.Div(
                    crispy.HTML(self.initial['email_list']),
                    css_class='col-sm-9 col-md-8 col-lg-6'
                ),
                css_id='emails-text',
                css_class='collapse form-group'
            ))

            fields.insert(5, crispy.Div(
                crispy.Div(
                    css_class='col-sm-3 col-md-2'
                ),
                crispy.Div(
                    StrictButton(
                        _("Show contact emails as text"),
                        type="button",
                        css_class='btn btn-default',
                        css_id='show_emails'
                    ),
                    crispy.HTML('<p class="help-block">%s</p>' %
                                _('Useful when you want to copy contact emails')),
                    css_class='col-sm-9 col-md-8 col-lg-6'
                ),
                css_class='form-group'
            ))

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Basic Information"),
                *fields
            ),
            crispy.Fieldset(
                _("Mailing Address"),
                'first_line',
                'second_line',
                'city',
                'state_province_region',
                'postal_code',
                crispy.Field('country', css_class="input-large",
                             data_countryname=COUNTRIES.get(self.current_country, '')),
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _("Update Billing Information"),
                    type="submit",
                    css_class='btn btn-primary',
                ),
            ),
        )

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

    def clean_email_list(self):
        return self.cleaned_data['email_list'].split(',')

    # Does not use the commit kwarg.
    # TODO - Should support it or otherwise change the function name
    @transaction.atomic
    def save(self, commit=True):
        billing_contact_info = super(EditBillingAccountInfoForm, self).save(commit=False)
        billing_contact_info.email_list = self.cleaned_data['email_list']
        billing_contact_info.account = self.account
        billing_contact_info.save()

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
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            'plan_edition',
            crispy.Fieldset(
                _("Basic Information"),
                'company_name',
                'first_name',
                'last_name',
                crispy.Field('email_list', css_class='input-xxlarge'),
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
                             data_countryname=COUNTRIES.get(self.current_country, ''))
            ),
            hqcrispy.FormActions(
                hqcrispy.LinkButton(_("Cancel"),
                                    reverse(DomainSubscriptionView.urlname,
                                            args=[self.domain]),
                                    css_class="btn btn-default"),
                StrictButton(_("Subscribe to Plan"),
                             type="submit",
                             css_class='btn btn-success disable-on-submit-no-spinner '
                                       'add-spinner-on-click'),
            ),
        )

    def save(self, commit=True):
        try:
            with transaction.atomic():
                account_save_success = super(ConfirmNewSubscriptionForm, self).save()
                if not account_save_success:
                    return False

                if self.current_subscription is not None:
                    if self.plan_version.plan.edition == SoftwarePlanEdition.COMMUNITY:
                        self.current_subscription.cancel_subscription(
                            adjustment_method=SubscriptionAdjustmentMethod.USER,
                            web_user=self.creating_user,
                        )
                    else:
                        subscription = self.current_subscription.change_plan(
                            self.plan_version,
                            web_user=self.creating_user,
                            adjustment_method=SubscriptionAdjustmentMethod.USER,
                            service_type=SubscriptionType.PRODUCT,
                            pro_bono_status=ProBonoStatus.NO,
                        )
                        subscription.is_active = True
                        if subscription.plan_version.plan.edition == SoftwarePlanEdition.ENTERPRISE:
                            subscription.do_not_invoice = True
                        subscription.save()
                else:
                    subscription = Subscription.new_domain_subscription(
                        self.account, self.domain, self.plan_version,
                        web_user=self.creating_user,
                        adjustment_method=SubscriptionAdjustmentMethod.USER,
                        service_type=SubscriptionType.PRODUCT,
                        pro_bono_status=ProBonoStatus.NO,
                        funding_source=FundingSource.CLIENT
                    )
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
        self.renewed_version = renewed_version
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
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
                _("Basic Information"),
                'company_name',
                'first_name',
                'last_name',
                crispy.Field('email_list', css_class='input-xxlarge'),
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
                             data_countryname=COUNTRIES.get(self.current_country, ''))
            ),
            crispy.Fieldset(
                _("Re-Confirm Product Agreement"),
                'confirm_legal',
            ),
            hqcrispy.FormActions(
                hqcrispy.LinkButton(
                    _("Cancel"),
                    reverse(DomainSubscriptionView.urlname, args=[self.domain]),
                    css_class="btn btn-default"
                ),
                StrictButton(
                    _("Renew Plan"),
                    type="submit",
                    css_class='btn btn-success',
                ),
            ),
        )

    def save(self, commit=True):
        try:
            with transaction.atomic():
                account_save_success = super(ConfirmSubscriptionRenewalForm, self).save()
                if not account_save_success:
                    return False

                for later_subscription in Subscription.objects.filter(
                    subscriber__domain=self.domain,
                    date_start__gt=self.current_subscription.date_start
                ).order_by('date_start').all():
                    later_subscription.date_start = datetime.date.today()
                    later_subscription.date_end = datetime.date.today()
                    later_subscription.save()
                    SubscriptionAdjustment.record_adjustment(
                        later_subscription,
                        reason=SubscriptionAdjustmentReason.CANCEL,
                        web_user=self.creating_user,
                        note="Cancelled due to changing subscription",
                    )

                self.current_subscription.renew_subscription(
                    web_user=self.creating_user,
                    adjustment_method=SubscriptionAdjustmentMethod.USER,
                    service_type=SubscriptionType.PRODUCT,
                    pro_bono_status=ProBonoStatus.NO,
                    funding_source=FundingSource.CLIENT,
                    new_version=self.renewed_version,
                )
        except SubscriptionRenewalError as e:
            log_accounting_error(
                "Subscription for %(domain)s failed to renew due to: %(error)s." % {
                    'domain': self.domain,
                    'error': e,
                }
            )
        return True


class ProBonoForm(forms.Form):
    contact_email = forms.EmailField(label=ugettext_lazy("Contact email"))
    organization = forms.CharField(label=ugettext_lazy("Organization"))
    project_overview = forms.CharField(widget=forms.Textarea, label="Project overview")
    pay_only_features_needed = forms.CharField(widget=forms.Textarea, label="Pay only features needed")
    duration_of_project = forms.CharField(help_text=ugettext_lazy(
        "We grant pro-bono subscriptions to match the duration of your "
        "project, up to a maximum of 12 months at a time (at which point "
        "you need to reapply)."
    ))
    domain = forms.CharField(label=ugettext_lazy("Project Space"))
    dimagi_contact = forms.CharField(
        help_text=ugettext_lazy("If you have already been in touch with someone from "
                    "Dimagi, please list their name."),
        required=False)
    num_expected_users = forms.CharField(label=ugettext_lazy("Number of expected users"))

    def __init__(self, use_domain_field, *args, **kwargs):
        super(ProBonoForm, self).__init__(*args, **kwargs)
        if not use_domain_field:
            self.fields['domain'].required = False
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
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
            hqcrispy.FormActions(
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
            recipient = settings.PROBONO_SUPPORT_EMAIL
            subject = "[Pro-Bono Application]"
            if domain is not None:
                subject = "%s %s" % (subject, domain)
            send_html_email_async.delay(subject, recipient, html_content, text_content=text_content,
                            email_from=settings.DEFAULT_FROM_EMAIL)
        except Exception:
            logging.error("Couldn't send pro-bono application email. "
                          "Contact: %s" % self.cleaned_data['contact_email']
            )


class InternalSubscriptionManagementForm(forms.Form):
    autocomplete_account_types = [
        BillingAccountType.CONTRACT,
        BillingAccountType.GLOBAL_SERVICES,
        BillingAccountType.USER_CREATED,
    ]

    @property
    def slug(self):
        raise NotImplementedError

    @property
    def subscription_type(self):
        raise NotImplementedError

    @property
    def account_name(self):
        raise NotImplementedError

    @property
    def account_emails(self):
        return []

    def process_subscription_management(self):
        raise NotImplementedError

    @property
    @memoized
    def next_account(self):
        matching_accounts = BillingAccount.objects.filter(
            name=self.account_name,
            account_type=BillingAccountType.GLOBAL_SERVICES,
        ).order_by('date_created')
        if matching_accounts:
            account = matching_accounts[0]
        else:
            account = BillingAccount(
                name=self.account_name,
                created_by=self.web_user,
                created_by_domain=self.domain,
                currency=Currency.get_default(),
                dimagi_contact=self.web_user,
                account_type=BillingAccountType.GLOBAL_SERVICES,
                entry_point=EntryPoint.CONTRACTED,
                pre_or_post_pay=PreOrPostPay.POSTPAY
            )
            account.save()
        contact_info, _ = BillingContactInfo.objects.get_or_create(account=account)
        for email in self.account_emails:
            if email not in contact_info.email_list:
                contact_info.email_list.append(email)
        contact_info.save()
        return account

    @property
    @memoized
    def current_subscription(self):
        return Subscription.get_subscribed_plan_by_domain(self.domain)[1]

    @property
    @memoized
    def should_autocomplete_account(self):
        return (
            self.current_subscription
            and self.current_subscription.account.account_type in self.autocomplete_account_types
        )

    @property
    @memoized
    def autocomplete_account_name(self):
        if self.should_autocomplete_account:
            return self.current_subscription.account.name
        return None

    @property
    @memoized
    def current_contact_emails(self):
        if self.should_autocomplete_account:
            try:
                return ','.join(self.current_subscription.account.billingcontactinfo.email_list)
            except BillingContactInfo.DoesNotExist:
                pass
        return None

    @property
    def subscription_default_fields(self):
        return {
            'internal_change': True,
            'web_user': self.web_user,
        }

    def __init__(self, domain, web_user, *args, **kwargs):
        super(InternalSubscriptionManagementForm, self).__init__(*args, **kwargs)
        self.domain = domain
        self.web_user = web_user

    @property
    def form_actions(self):
        return (
            crispy.Hidden('slug', self.slug),
            hqcrispy.FormActions(
                crispy.Submit(
                    self.slug,
                    ugettext_noop('Update'),
                    css_class='disable-on-submit',
                ),
            ),
        )


class DimagiOnlyEnterpriseForm(InternalSubscriptionManagementForm):
    slug = 'dimagi_only_enterprise'
    subscription_type = ugettext_noop('Test or Demo Project')

    def __init__(self, domain, web_user, *args, **kwargs):
        super(DimagiOnlyEnterpriseForm, self).__init__(domain, web_user, *args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.HTML(ugettext_noop(
                '<i class="fa fa-info-circle"></i> You will have access to all '
                'features for free as soon as you hit "Update".  Please make '
                'sure this is an internal Dimagi test space, not in use by a '
                'partner.'
            )),
            *self.form_actions
        )

    @transaction.atomic
    def process_subscription_management(self):
        enterprise_plan_version = DefaultProductPlan.get_default_plan_by_domain(
            self.domain, SoftwarePlanEdition.ENTERPRISE
        ).plan.get_version()
        if self.current_subscription:
            self.current_subscription.change_plan(
                enterprise_plan_version,
                account=self.next_account,
                transfer_credits=self.current_subscription.account == self.next_account,
                **self.subscription_default_fields
            )
        else:
            Subscription.new_domain_subscription(
                self.next_account,
                self.domain,
                enterprise_plan_version,
                **self.subscription_default_fields
            )

    @property
    def subscription_default_fields(self):
        fields = super(DimagiOnlyEnterpriseForm, self).subscription_default_fields
        fields.update({
            'do_not_invoice': True,
            'service_type': SubscriptionType.INTERNAL,
        })
        return fields

    @property
    def account_name(self):
        return "Dimagi Internal Test Account for Project %s" % self.domain


class AdvancedExtendedTrialForm(InternalSubscriptionManagementForm):
    slug = 'advanced_extended_trial'
    subscription_type = ugettext_noop('Extended Trial')

    organization_name = forms.CharField(
        label=ugettext_noop('Organization Name'),
        max_length=BillingAccount._meta.get_field('name').max_length,
    )

    emails = forms.CharField(
        label=ugettext_noop('Partner Contact Emails'),
    )

    trial_length = forms.ChoiceField(
        choices=[(days, "%d days" % days) for days in [30, 60, 90]],
        label="Trial Length",
    )

    def __init__(self, domain, web_user, *args, **kwargs):
        super(AdvancedExtendedTrialForm, self).__init__(domain, web_user, *args, **kwargs)

        self.fields['organization_name'].initial = self.autocomplete_account_name
        self.fields['emails'].initial = self.current_contact_emails

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Field('organization_name'),
            crispy.Field('emails', css_class='input-xxlarge'),
            crispy.Field('trial_length', data_bind='value: trialLength'),
            crispy.Div(
                crispy.Div(
                    crispy.HTML(_(
                        '<p><i class="fa fa-info-circle"></i> The trial includes '
                        'access to all features, 5 mobile workers, and 25 SMS.  Fees '
                        'apply for users or SMS in excess of these limits (1 '
                        'USD/user/month, regular SMS fees).</p>'
                    )),
                    crispy.HTML(_(
                        '<p><i class="fa fa-info-circle"></i> The trial will begin as soon '
                        'as you hit "Update" and end on <span data-bind="text: end_date"></span>.  '
                        'On <span data-bind="text: end_date"></span> '
                        'the project space will automatically be subscribed to the '
                        'Community plan.</p>'
                    )),
                    css_class='col-sm-offset-3 col-md-offset-2'
                ),
                css_class='form-group'
            ),
            *self.form_actions
        )

    @transaction.atomic
    def process_subscription_management(self):
        advanced_trial_plan_version = DefaultProductPlan.get_default_plan_by_domain(
            self.domain, edition=SoftwarePlanEdition.ADVANCED, is_trial=True,
        )
        if self.current_subscription:
            self.current_subscription.change_plan(
                advanced_trial_plan_version,
                account=self.next_account,
                transfer_credits=self.current_subscription.account == self.next_account,
                **self.subscription_default_fields
            )
        else:
            Subscription.new_domain_subscription(
                self.next_account,
                self.domain,
                advanced_trial_plan_version,
                **self.subscription_default_fields
            )

    @property
    def subscription_default_fields(self):
        fields = super(AdvancedExtendedTrialForm, self).subscription_default_fields
        fields.update({
            'auto_generate_credits': False,
            'date_end': datetime.date.today() + relativedelta(days=int(self.cleaned_data['trial_length'])),
            'do_not_invoice': False,
            'is_trial': True,
            'service_type': SubscriptionType.EXTENDED_TRIAL
        })
        return fields

    @property
    def account_name(self):
        return self.cleaned_data['organization_name']

    @property
    def account_emails(self):
        return self.cleaned_data['emails'].split(',')


class ContractedPartnerForm(InternalSubscriptionManagementForm):
    slug = 'contracted_partner'
    subscription_type = ugettext_noop('Contracted Partner')

    software_plan_edition = forms.ChoiceField(
        choices=(
            (SoftwarePlanEdition.STANDARD, SoftwarePlanEdition.STANDARD),
            (SoftwarePlanEdition.PRO, SoftwarePlanEdition.PRO),
            (SoftwarePlanEdition.ADVANCED, SoftwarePlanEdition.ADVANCED),
        ),
        label=ugettext_noop('Software Plan'),
    )

    fogbugz_client_name = forms.CharField(
        label=ugettext_noop('Fogbugz Client Name'),
        max_length=BillingAccount._meta.get_field('name').max_length,
    )

    emails = forms.CharField(
        help_text=ugettext_noop(
            'This is who will receive invoices if the Client exceeds the user '
            'or SMS limits in their plan.'
        ),
        label=ugettext_noop('Partner Contact Emails'),
    )

    start_date = forms.DateField(
        help_text=ugettext_noop('Date the project needs access to features.'),
        label=ugettext_noop('Start Date'),
    )

    end_date = forms.DateField(
        help_text=ugettext_noop(
            '1 year after the deployment date (date the project goes live).'
        ),
        label=ugettext_noop('End Date'),
    )

    sms_credits = forms.DecimalField(
        initial=0,
        label=ugettext_noop('SMS Credits'),
    )

    user_credits = forms.IntegerField(
        initial=0,
        label=ugettext_noop('User Credits'),
    )

    def __init__(self, domain, web_user, *args, **kwargs):
        super(ContractedPartnerForm, self).__init__(domain, web_user, *args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.fields['fogbugz_client_name'].initial = self.autocomplete_account_name
        self.fields['emails'].initial = self.current_contact_emails

        plan_edition = self.current_subscription.plan_version.plan.edition if self.current_subscription else None

        if self.is_uneditable:
            self.helper.layout = crispy.Layout(
                hqcrispy.B3TextField('software_plan_edition', plan_edition),
                hqcrispy.B3TextField('fogbugz_client_name', self.current_subscription.account.name),
                hqcrispy.B3TextField('emails', self.current_contact_emails),
                hqcrispy.B3TextField('start_date', self.current_subscription.date_start),
                hqcrispy.B3TextField('end_date', self.current_subscription.date_end),
                crispy.HTML(_(
                    '<p><i class="fa fa-info-circle"></i> This project is on a contracted Enterprise '
                    'subscription. You cannot change contracted Enterprise subscriptions here. '
                    'Please contact the Ops team at %(accounts_email)s to request changes.</p>' % {
                        'accounts_email': settings.ACCOUNTS_EMAIL,
                    }
                ))
            )
        elif plan_edition not in [
            first for first, second in self.fields['software_plan_edition'].choices
        ]:
            self.fields['start_date'].initial = datetime.date.today()
            self.fields['end_date'].initial = datetime.date.today() + relativedelta(years=1)
            self.helper.layout = crispy.Layout(
                hqcrispy.B3TextField('software_plan_edition', plan_edition),
                crispy.Field('software_plan_edition'),
                crispy.Field('fogbugz_client_name'),
                crispy.Field('emails'),
                crispy.Field('start_date', css_class='date-picker'),
                crispy.Field('end_date', css_class='date-picker'),
                crispy.Field('sms_credits'),
                crispy.Field('user_credits'),
                crispy.Div(
                    crispy.Div(
                        crispy.HTML(
                            _('<p><i class="fa fa-info-circle"></i> '
                              'Clicking "Update" will set up the '
                              'subscription in CommCareHQ to one of our '
                              'standard contracted plans.<br/> If you '
                              'need to set up a non-standard plan, '
                              'please email {}.</p>').format(settings.ACCOUNTS_EMAIL)
                        ),
                        css_class='col-sm-offset-3 col-md-offset-2'
                    ),
                    css_class='form-group'
                ),
                *self.form_actions
            )
        else:
            self.fields['end_date'].initial = self.current_subscription.date_end
            self.fields['software_plan_edition'].initial = plan_edition
            self.helper.layout = crispy.Layout(
                crispy.Field('software_plan_edition'),
                crispy.Field('fogbugz_client_name'),
                crispy.Field('emails'),
                hqcrispy.B3TextField('start_date', self.current_subscription.date_start),
                crispy.Hidden('start_date', self.current_subscription.date_start),
                crispy.Field('end_date', css_class='date-picker'),
                crispy.Hidden('sms_credits', 0),
                crispy.Hidden('user_credits', 0),
                crispy.HTML(_(
                    '<div class="alert alert-warning">'
                    '<p><strong>Are you sure you want to extend the subscription?</strong></p>'
                    '<p>If this project is becoming a self-service project and only paying for '
                    'hosting fees, please have them self-subscribe through the subscription page.  '
                    'Please use this page only to extend the existing services contract.</p>'
                    '</div>'
                )),
                *self.form_actions
            )

    @transaction.atomic
    def process_subscription_management(self):
        new_plan_version = None
        edition = self.cleaned_data['software_plan_edition']
        for plan_version in SoftwarePlanVersion.objects.filter(plan__edition=edition).order_by('-date_created'):
            privileges = get_privileges(plan_version)
            if (
                REPORT_BUILDER_5 in privileges
                and not (REPORT_BUILDER_ADD_ON_PRIVS - {REPORT_BUILDER_5, REPORT_BUILDER_TRIAL}) & privileges
            ):
                new_plan_version = plan_version
                break
        if not new_plan_version:
            log_accounting_error(
                "CommCare %s edition with privilege REPORT_BUILDER_5 was not found! Requires manual setup."
                % edition
            )
            new_plan_version = DefaultProductPlan.get_default_plan_by_domain(
                self.domain, edition=self.cleaned_data['software_plan_edition'],
            )

        if (
            self.current_subscription
            and self.current_subscription.service_type == SubscriptionType.IMPLEMENTATION
            and self.current_subscription.plan_version == new_plan_version
            and self.current_subscription.date_start == self.cleaned_data['start_date']
        ):
            contracted_subscription = self.current_subscription
            contracted_subscription.account = self.next_account
            contracted_subscription.update_subscription(
                contracted_subscription.date_start,
                **{k: v for k, v in self.subscription_default_fields.items() if k != 'internal_change'}
            )
        elif not self.current_subscription or self.cleaned_data['start_date'] > datetime.date.today():
            contracted_subscription = Subscription.new_domain_subscription(
                self.next_account,
                self.domain,
                new_plan_version,
                date_start=self.cleaned_data['start_date'],
                **self.subscription_default_fields
            )
        else:
            contracted_subscription = self.current_subscription.change_plan(
                new_plan_version,
                transfer_credits=self.current_subscription.account == self.next_account,
                account=self.next_account,
                **self.subscription_default_fields
            )

        CreditLine.add_credit(
            self.cleaned_data['sms_credits'],
            feature_type=FeatureType.SMS,
            subscription=contracted_subscription,
            web_user=self.web_user,
            reason=CreditAdjustmentReason.MANUAL,
        )
        CreditLine.add_credit(
            self.cleaned_data['user_credits'],
            feature_type=FeatureType.USER,
            subscription=contracted_subscription,
            web_user=self.web_user,
            reason=CreditAdjustmentReason.MANUAL,
        )

    @property
    def is_uneditable(self):
        return (
            self.current_subscription
            and self.current_subscription.plan_version.plan.edition == SoftwarePlanEdition.ENTERPRISE
            and self.current_subscription.service_type == SubscriptionType.IMPLEMENTATION
        )

    @property
    def subscription_default_fields(self):
        fields = super(ContractedPartnerForm, self).subscription_default_fields
        fields.update({
            'auto_generate_credits': True,
            'date_end': self.cleaned_data['end_date'],
            'do_not_invoice': False,
            'service_type': SubscriptionType.IMPLEMENTATION,
        })
        return fields

    @property
    def account_name(self):
        return self.cleaned_data['fogbugz_client_name']

    @property
    def account_emails(self):
        return self.cleaned_data['emails'].split(',')

    def clean_end_date(self):
        end_date = self.cleaned_data['end_date']
        if end_date < datetime.date.today():
            raise forms.ValidationError(_(
                'End Date cannot be a past date.'
            ))
        if end_date > datetime.date.today() + relativedelta(years=5):
            raise forms.ValidationError(_(
                'This contract is too long to be managed in this interface.  '
                'Please contact %(email)s to manage a contract greater than '
                '5 years.'
            ) % {
                'email': settings.ACCOUNTS_EMAIL,
            })
        return end_date

    def clean_sms_credits(self):
        return self._clean_credits(self.cleaned_data['sms_credits'], 10000, _('SMS'))

    def clean_user_credits(self):
        return self._clean_credits(self.cleaned_data['user_credits'], 2000, _('user'))

    def _clean_credits(self, credits, max_credits, credits_name):
        if credits > max_credits:
            raise forms.ValidationError(_(
                'You tried to add too much %(credits_name)s credit!  Only '
                'someone on the operations team can add that much credit.  '
                'Please reach out to %(email)s.'
            ) % {
                'credits_name': credits_name,
                'email': settings.ACCOUNTS_EMAIL,
            })
        return credits


INTERNAL_SUBSCRIPTION_MANAGEMENT_FORMS = [
    ContractedPartnerForm,
    DimagiOnlyEnterpriseForm,
    AdvancedExtendedTrialForm,
]


class SelectSubscriptionTypeForm(forms.Form):
    subscription_type = forms.ChoiceField(
        choices=[
            ('', ugettext_noop('Select a subscription type...'))
        ] + [
            (form.slug, form.subscription_type)
            for form in INTERNAL_SUBSCRIPTION_MANAGEMENT_FORMS
        ],
        label=ugettext_noop('Subscription Type'),
        required=False,
    )

    def __init__(self, defaults=None, disable_input=False, **kwargs):
        defaults = defaults or {}
        super(SelectSubscriptionTypeForm, self).__init__(defaults, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        if defaults and disable_input:
            self.helper.layout = crispy.Layout(
                hqcrispy.B3TextField(
                    'subscription_type', {
                        form.slug: form.subscription_type
                        for form in INTERNAL_SUBSCRIPTION_MANAGEMENT_FORMS
                    }[defaults.get('subscription_type')]
                ),
            )
        else:
            self.helper.layout = crispy.Layout(
                crispy.Field(
                    'subscription_type',
                    data_bind='value: subscriptionType',
                    css_class="disabled"
                )
            )
