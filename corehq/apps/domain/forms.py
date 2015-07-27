import copy
import logging
from urlparse import urlparse, parse_qs
import datetime
import dateutil
from dateutil.relativedelta import relativedelta
import re
import io
from PIL import Image
import uuid
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.models import get_current_site
from django.utils.http import urlsafe_base64_encode
from dimagi.utils.decorators.memoized import memoized
from django.contrib.auth import get_user_model
from django.db import transaction
from corehq import privileges
from corehq.apps.accounting.exceptions import SubscriptionRenewalError
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.sms.phonenumbers_helper import parse_phone_number
from corehq.feature_previews import CALLCENTER
import settings

from django import forms
from crispy_forms.bootstrap import FormActions, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from django.core.urlresolvers import reverse

from django.forms.fields import (ChoiceField, CharField, BooleanField,
    ImageField)
from django.forms.widgets import  Select
from django.utils.encoding import smart_str, force_bytes
from django.utils.safestring import mark_safe
from django_countries.data import COUNTRIES
from corehq.apps.accounting.models import (
    BillingAccount,
    BillingAccountType,
    BillingContactInfo,
    CreditAdjustmentReason,
    CreditLine,
    Currency,
    DefaultProductPlan,
    FeatureType,
    ProBonoStatus,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionAdjustmentMethod,
    SubscriptionType,
    EntryPoint,
)
from corehq.apps.app_manager.models import (Application, RemoteApp,
                                            FormBase, get_apps_in_domain)

from corehq.apps.domain.models import (LOGO_ATTACHMENT, LICENSES, DATA_DICT,
    AREA_CHOICES, SUB_AREA_CHOICES, BUSINESS_UNITS, Domain, TransferDomainRequest)
from corehq.apps.reminders.models import CaseReminderHandler

from corehq.apps.users.models import WebUser, CommCareUser
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.crispy import TextField
from corehq.apps.hqwebapp.tasks import send_mail_async, send_html_email_async
from corehq.util.timezones.fields import TimeZoneField
from corehq.util.timezones.forms import TimeZoneChoiceField
from django.template.loader import render_to_string
from django.utils.translation import ugettext_noop, ugettext as _, ugettext_lazy
from corehq.apps.style.forms.widgets import BootstrapCheckboxInput, BootstrapDisabledInput
import django

if django.VERSION < (1, 6):
    from django.contrib.auth.hashers import UNUSABLE_PASSWORD as UNUSABLE_PASSWORD_PREFIX
else:
    from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX

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
        self.helper.layout = crispy.Layout(
            'publish',
            'name',
            'description',
            'deployment_date',
            'phone_model',
            'user_type',
            'attribution_notes',
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
            'publish',
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
                'share_multimedia',
                'share_reminders',
            ),
            crispy.Fieldset(
                'Licensing',
                'license',
                'cda_confirmed',
            ),
        )

        if self.is_superuser:
            self.helper.layout.append(crispy.Fieldset('Starter App', 'is_starter_app',),)


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
    hr_name = forms.CharField(label=ugettext_lazy("Project Name"))
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
        domain = kwargs.pop('domain', None)
        self.can_use_custom_logo = kwargs.pop('can_use_custom_logo', False)
        super(DomainGlobalSettingsForm, self).__init__(*args, **kwargs)
        if not self.can_use_custom_logo:
            del self.fields['logo']
            del self.fields['delete_logo']

        if domain:
            if not CALLCENTER.enabled(domain):
                self.fields['call_center_enabled'].widget = forms.HiddenInput()
                self.fields['call_center_case_owner'].widget = forms.HiddenInput()
                self.fields['call_center_case_type'].widget = forms.HiddenInput()
            else:
                groups = Group.get_case_sharing_groups(domain)
                users = CommCareUser.by_domain(domain)

                call_center_user_choices = [
                    (user._id, user.raw_username + ' [user]') for user in users
                ]
                call_center_group_choices = [
                    (group._id, group.name + ' [group]') for group in groups
                ]

                self.fields["call_center_case_owner"].choices = \
                    [('', '')] + \
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
                 not cleaned_data.get('call_center_case_owner'))):
            raise forms.ValidationError(_(
                'You must choose an Owner and Case Type to use the call center application. '
                'Please uncheck the "Call Center Application" setting or enter values for the other fields.'
            ))

        return cleaned_data

    def save(self, request, domain):
        domain.hr_name = self.cleaned_data['hr_name']

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

        domain.call_center_config.enabled = self.cleaned_data.get('call_center_enabled', False)
        if domain.call_center_config.enabled:
            domain.internal.using_call_center = True
            domain.call_center_config.case_owner_id = self.cleaned_data.get('call_center_case_owner', None)
            domain.call_center_config.case_type = self.cleaned_data.get('call_center_case_type', None)

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
        user = kwargs.pop('user', None)
        domain = kwargs.get('domain', None)
        super(DomainMetadataForm, self).__init__(*args, **kwargs)

        project = Domain.get_by_name(domain)
        if project.cloudcare_releases == 'default' or not domain_has_privilege(domain, privileges.CLOUDCARE):
            # if the cloudcare_releases flag was just defaulted, don't bother showing
            # this setting at all
            self.fields['cloudcare_releases'].widget = forms.HiddenInput()

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
        help_text=ugettext_lazy("If access to a project space is restricted only users added " +
                    "to the domain and staff members will have access.")
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

    def save(self, domain):
        domain.restrict_superusers = self.cleaned_data.get('restrict_superusers', False)
        secure_submissions = self.cleaned_data.get(
            'secure_submissions', False)
        apps_to_save = []
        if secure_submissions != domain.secure_submissions:
            for app in get_apps_in_domain(domain.name):
                if app.secure_submissions != secure_submissions:
                    app.secure_submissions = secure_submissions
                    apps_to_save.append(app)
        domain.secure_submissions = secure_submissions
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
                crispy.Div(*additional_fields),
            ),
            crispy.Fieldset(
                _("Salesforce Details"),
                'sf_contract_id',
                'sf_account_id',
                'services',
            ),
            FormActions(
                StrictButton(
                    _("Update Project Information"),
                    type="submit",
                    css_class='btn btn-primary',
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
            business_unit=self.cleaned_data['business_unit'],
            **kwargs
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


class HQPasswordResetForm(forms.Form):
    """
    Only finds users and emails forms where the USERNAME is equal to the
    email specified (preventing Mobile Workers from using this form to submit).

    This small change is why we can't use the default PasswordReset form.
    """
    email = forms.EmailField(label=ugettext_lazy("Username"), max_length=254)
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


class EditBillingAccountInfoForm(forms.ModelForm):

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

        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.layout = crispy.Layout(
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
                             data_countryname=COUNTRIES.get(self.current_country, '')),
            ),
            FormActions(
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

    def save(self, commit=True):
        billing_contact_info = super(EditBillingAccountInfoForm, self).save(commit=False)
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
        self.helper.layout = crispy.Layout(
            'plan_edition',
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
                             data_countryname=COUNTRIES.get(self.current_country, ''))
            ),
            FormActions(
                crispy.HTML('<a href="%(url)s" style="margin-right:5px;" class="btn">%(title)s</a>' % {
                    'url': reverse(DomainSubscriptionView.urlname, args=[self.domain]),
                    'title': _("Cancel"),
                }),
                StrictButton(
                    _("Subscribe to Plan"),
                    type="submit",
                    css_class='btn btn-success disable-on-submit-no-spinner add-spinner-on-click',
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
                        self.plan_version,
                        web_user=self.creating_user,
                        adjustment_method=SubscriptionAdjustmentMethod.USER,
                        service_type=SubscriptionType.SELF_SERVICE,
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
                    service_type=SubscriptionType.SELF_SERVICE)
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
                             data_countryname=COUNTRIES.get(self.current_country, ''))
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
                service_type=SubscriptionType.SELF_SERVICE,
                pro_bono_status=ProBonoStatus.NO,
                new_version=self.renewed_version,
            )
        except SubscriptionRenewalError as e:
            logger.error("[BILLING] Subscription for %(domain)s failed to "
                         "renew due to: %(error)s." % {
                             'domain': self.domain,
                             'error': e,
                         })
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
            )
            account.save()
        contact_info, _ = BillingContactInfo.objects.get_or_create(account=account)
        emails = contact_info.emails.split(',') if contact_info.emails else []
        for email in self.account_emails:
            if email not in emails:
                emails.append(email)
        contact_info.emails = ','.join(emails)
        contact_info.save()
        return account

    @property
    @memoized
    def current_subscription(self):
        return Subscription.get_subscribed_plan_by_domain(self.domain)[1]

    @property
    @memoized
    def autocomplete_account_name(self):
        if (
            self.current_subscription
            and self.current_subscription.account.account_type in self.autocomplete_account_types
        ):
            return self.current_subscription.account.name
        return None

    @property
    @memoized
    def current_contact_emails(self):
        if self.current_subscription is None:
            return None
        try:
            return BillingContactInfo.objects.get(
                account=self.current_subscription.account,
                account__account_type__in=self.autocomplete_account_types,
            ).emails
        except BillingContactInfo.DoesNotExist:
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
        return FormActions(
            crispy.ButtonHolder(
                crispy.Submit(
                    self.slug,
                    ugettext_noop('Update')
                )
            )
        )


class DimagiOnlyEnterpriseForm(InternalSubscriptionManagementForm):
    slug = 'dimagi_only_enterprise'
    subscription_type = ugettext_noop('Test or Demo Project')

    def __init__(self, domain, web_user, *args, **kwargs):
        super(DimagiOnlyEnterpriseForm, self).__init__(domain, web_user, *args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.layout = crispy.Layout(
            crispy.HTML(ugettext_noop(
                '<i class="icon-info-sign"></i> You will have access to all '
                'features for free as soon as you hit "Update".  Please make '
                'sure this is an internal Dimagi test space, not in use by a '
                'partner.'
            )),
            self.form_actions
        )

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
        })
        return fields

    @property
    def account_name(self):
        return "Dimagi Internal Test Account for Project %s" % self.domain


class AdvancedExtendedTrialForm(InternalSubscriptionManagementForm):
    slug = 'advanced_extended_trial'
    subscription_type = ugettext_noop('3 Month Trial')

    organization_name = forms.CharField(
        label=ugettext_noop('Organization Name'),
        max_length=BillingAccount._meta.get_field('name').max_length,
    )

    emails = forms.CharField(
        label=ugettext_noop('Partner Contact Emails'),
        max_length=BillingContactInfo._meta.get_field('emails').max_length
    )

    end_date = forms.DateField(
        widget=forms.HiddenInput,
    )

    def __init__(self, domain, web_user, *args, **kwargs):
        end_date = datetime.date.today() + relativedelta(months=3)
        kwargs['initial'] = {
            'end_date': end_date,
        }

        super(AdvancedExtendedTrialForm, self).__init__(domain, web_user, *args, **kwargs)

        self.fields['organization_name'].initial = self.autocomplete_account_name
        self.fields['emails'].initial = self.current_contact_emails

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.layout = crispy.Layout(
            crispy.Field('organization_name'),
            crispy.Field('emails', css_class='input-xxlarge'),
            crispy.Field('end_date'),
            crispy.HTML(_(
                '<p><i class="icon-info-sign"></i> The 3 month trial includes '
                'access to all features, 5 mobile workers, and 25 SMS.  Fees '
                'apply for users or SMS in excess of these limits (1 '
                'USD/user/month, regular SMS fees).</p>'
            )),
            crispy.HTML(_(
                '<p><i class="icon-info-sign"></i> The trial will begin as soon '
                'as you hit "Update" and end on %(end_date)s.  On %(end_date)s '
                ' the project space will automatically be subscribed to the '
                'Community plan.</p>'
            ) % {
                'end_date': end_date,
            }),
            self.form_actions
        )

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
            'date_end': self.cleaned_data['end_date'],
            'do_not_invoice': False,
            'is_trial': True,
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
        max_length=BillingContactInfo._meta.get_field('emails').max_length,
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
        self.fields['fogbugz_client_name'].initial = self.autocomplete_account_name
        self.fields['emails'].initial = self.current_contact_emails

        plan_edition = self.current_subscription.plan_version.plan.edition if self.current_subscription else None
        if plan_edition not in [
            first for first, second in self.fields['software_plan_edition'].choices
        ]:
            self.fields['start_date'].initial = datetime.date.today()
            self.fields['end_date'].initial = datetime.date.today() + relativedelta(years=1)
            self.helper.layout = crispy.Layout(
                crispy.Field('software_plan_edition'),
                crispy.Field('fogbugz_client_name'),
                crispy.Field('emails', css_class='input-xxlarge'),
                crispy.Field('start_date', css_class='date-picker'),
                crispy.Field('end_date', css_class='date-picker'),
                crispy.Field('sms_credits'),
                crispy.Field('user_credits'),
                crispy.HTML(_(
                    '<p><i class="icon-info-sign"></i> Clicking "Update" will set '
                    'up the subscription in CommCareHQ to one of our standard '
                    'contracted plans.  If you need to set up a non-standard plan, '
                    'please email %(accounts_email)s.</p>') % {
                        'accounts_email': settings.ACCOUNTS_EMAIL,
                    }
                ),
                self.form_actions
            )
        else:
            self.fields['end_date'].initial = self.current_subscription.date_end
            self.helper.layout = crispy.Layout(
                TextField('software_plan_edition', plan_edition),
                crispy.Hidden('software_plan_edition', plan_edition),
                crispy.Field('fogbugz_client_name'),
                crispy.Field('emails', css_class='input-xxlarge'),
                TextField('start_date', self.current_subscription.date_start),
                crispy.Hidden('start_date', self.current_subscription.date_start),
                crispy.Field('end_date', css_class='date-picker'),
                crispy.Hidden('sms_credits', 0),
                crispy.Hidden('user_credits', 0),
                crispy.HTML(_(
                    '<div class="alert">'
                    '<p><strong>Are you sure you want to extend the subscription?</strong></p>'
                    '<p>If this project is becoming a self-service project and only paying for '
                    'hosting fees, please have them self-subscribe through the subscription page.  '
                    'Please use this page only to extend the existing services contract.</p>'
                    '</div>'
                )),
                self.form_actions
            )

    def process_subscription_management(self):
        new_plan_version = DefaultProductPlan.get_default_plan_by_domain(
            self.domain, edition=self.cleaned_data['software_plan_edition'],
        )

        if not self.current_subscription or self.cleaned_data['start_date'] > datetime.date.today():
            with transaction.atomic():
                # atomically create new subscription
                new_subscription = Subscription.new_domain_subscription(
                    self.next_account,
                    self.domain,
                    new_plan_version,
                    date_start=self.cleaned_data['start_date'],
                    **self.subscription_default_fields
                )
        else:
            # change plan method is already atomic
            new_subscription = self.current_subscription.change_plan(
                new_plan_version,
                transfer_credits=self.current_subscription.account == self.next_account,
                account=self.next_account,
                **self.subscription_default_fields
            )

        CreditLine.add_credit(
            self.cleaned_data['sms_credits'],
            feature_type=FeatureType.SMS,
            subscription=new_subscription,
            web_user=self.web_user,
            reason=CreditAdjustmentReason.MANUAL,
        )
        CreditLine.add_credit(
            self.cleaned_data['user_credits'],
            feature_type=FeatureType.USER,
            subscription=new_subscription,
            web_user=self.web_user,
            reason=CreditAdjustmentReason.MANUAL,
        )

    @property
    def subscription_default_fields(self):
        fields = super(ContractedPartnerForm, self).subscription_default_fields
        fields.update({
            'auto_generate_credits': True,
            'date_end': self.cleaned_data['end_date'],
            'do_not_invoice': False,
            'service_type': SubscriptionType.CONTRACTED,
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

    def __init__(self, *args, **kwargs):
        super(SelectSubscriptionTypeForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.layout = crispy.Layout(
            crispy.Field(
                'subscription_type',
                data_bind='value: subscriptionType',
            )
        )
