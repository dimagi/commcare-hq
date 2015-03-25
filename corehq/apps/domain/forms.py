import copy
import logging
from urlparse import urlparse, parse_qs
import dateutil
import re
import io
from PIL import Image
import uuid
from django.contrib.auth import get_user_model
from corehq import privileges, toggles
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
    ImageField, DecimalField, IntegerField)
from django.forms.widgets import  Select
from django.utils.encoding import smart_str
from django.contrib.auth.forms import PasswordResetForm
from django.utils.safestring import mark_safe
from django_countries.countries import COUNTRIES
from corehq.apps.accounting.models import (
    BillingAccountAdmin,
    BillingContactInfo,
    ProBonoStatus,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionAdjustmentMethod,
    SubscriptionType,
)
from corehq.apps.app_manager.models import (Application, RemoteApp,
                                            FormBase, get_apps_in_domain)

from corehq.apps.domain.models import (LOGO_ATTACHMENT, LICENSES, DATA_DICT,
    AREA_CHOICES, SUB_AREA_CHOICES, Domain, TransferDomainRequest)
from corehq.apps.reminders.models import CaseReminderHandler

from corehq.apps.users.models import WebUser, CommCareUser
from corehq.apps.groups.models import Group
from dimagi.utils.django.email import send_HTML_email
from corehq.util.timezones.fields import TimeZoneField
from corehq.util.timezones.forms import TimeZoneChoiceField
from django.template.loader import render_to_string
from django.utils.translation import ugettext_noop, ugettext as _
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


class SnapshotFixtureForm(forms.Form):
    publish = BooleanField(label=ugettext_noop("Publish?"), required=False)
    description = CharField(label=ugettext_noop("Description"), required=False, widget=forms.Textarea,
        help_text=ugettext_noop("A detailed technical description of the table"))

    def __init__(self, *args, **kwargs):
        super(SnapshotFixtureForm, self).__init__(*args, **kwargs)
        self.fields.keyOrder = [
            'publish',
            'description',
        ]


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
    video = CharField(label=ugettext_noop("Youtube Video"), required=False,
        help_text=ugettext_noop("An optional youtube clip to tell users about your app. Please copy and paste a URL to a youtube video"))
    documentation_file = forms.FileField(label=ugettext_noop("Documentation File"), required=False,
        help_text=ugettext_noop("An optional file to tell users more about your app."))
    cda_confirmed = BooleanField(required=False, label=ugettext_noop("Content Distribution Agreement"))

    def __init__(self, *args, **kw):
        self.dom = kw.pop("domain", None)
        user = kw.pop("user", None)
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

        if self.dom and toggles.DOCUMENTATION_FILE.enabled(user.username):
            self.fields.keyOrder.insert(5, 'documentation_file')

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
    USER_DNE = _(u'The user being transferred to does not exist')
    DOMAIN_MISMATCH = _(u'Mismatch in domains when confirming')


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
        required=False,
        # Hide the case type, but keep the form field in order to preserve
        # existing values on update.
        widget=forms.HiddenInput()
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

            domain.call_center_config.enabled = self.cleaned_data.get('call_center_enabled', False)
            if domain.call_center_config.enabled:
                domain.internal.using_call_center = True
                domain.call_center_config.case_owner_id = self.cleaned_data.get('call_center_case_owner', None)
                domain.call_center_config.case_type = self.cleaned_data.get('call_center_case_type') or 'user-case'

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
        except Exception:
            return False


class DomainMetadataForm(DomainGlobalSettingsForm):

    cloudcare_releases = ChoiceField(
        label=_("CloudCare should use"),
        initial=None,
        required=False,
        choices=(
            ('stars', _('Latest starred version')),
            ('nostars', _('Highest numbered version (not recommended)')),
        ),
        help_text=_("Choose whether CloudCare should use the latest "
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
        label=_("Restrict Dimagi Staff Access"),
        required=False,
        help_text=_("If access to a project space is restricted only users added " +
                    "to the domain and staff members will have access.")
    )
    secure_submissions = BooleanField(
        label=_("Secure submissions"),
        required=False,
        help_text=_(mark_safe(
            "Secure Submissions prevents others from impersonating your mobile workers."
            "This setting requires all deployed applications to be using secure "
            "submissions as well. "
            "<a href='https://help.commcarehq.org/display/commcarepublic/Project+Space+Settings'>"
            "Read more about secure submissions here</a>"))
    )

    def save(self, domain):
        domain.restrict_superusers = self.cleaned_data.get('restrict_superusers', False)
        try:
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
        except Exception:
            return False


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
        label=_("Real Project"),
        choices=(('true', _('Test')),
                 ('false', _('Real')),
                 ('none', _('unknown')))
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
        help_text=_("Quick 1-2 sentence summary of the project."),
    )
    notes = CharField(label=ugettext_noop("Notes*"), required=False, widget=forms.Textarea)
    phone_model = CharField(
        label=ugettext_noop("Device Model"),
        help_text=_("Add CloudCare, if this project is using CloudCare as well"),
        required=False,
    )
    deployment_date = CharField(
        label=ugettext_noop("Deployment date"),
        required=False,
        help_text=_("Date that the project went live (usually right after training).")
    )
    countries = forms.MultipleChoiceField(
        label=ugettext_noop("Countries"),
        choices=COUNTRIES,
    )
    commtrack_domain = ChoiceField(
        label=ugettext_noop("CommCare Supply Project"),
        choices=tf_choices('Yes', 'No'),
        required=False,
        help_text=_("This app aims to improve the supply of goods and materials")
    )

    def __init__(self, can_edit_eula, *args, **kwargs):
        super(DomainInternalForm, self).__init__(*args, **kwargs)
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
                'countries',
                'commtrack_domain',
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
        self.can_edit_eula = can_edit_eula
        if self.can_edit_eula:
            self.fields['custom_eula'] = ChoiceField(
                label=ugettext_noop("Custom Eula?"),
                choices=tf_choices('Yes', 'No'),
                required=False,
                help_text='Set to "yes" if this project has a customized EULA as per their contract.'
            )
            self.fields['can_use_data'] = ChoiceField(
                label=ugettext_noop("Can use project data?"),
                choices=tf_choices('Yes', 'No'),
                required=False,
                help_text='Set to "no" if this project opts out of data usage. Defaults to "yes".'
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
        if any((user.password == UNUSABLE_PASSWORD_PREFIX)
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
                service_type=SubscriptionType.SELF_SERVICE,
                pro_bono_status=ProBonoStatus.NO,
            )
        except SubscriptionRenewalError as e:
            logger.error("[BILLING] Subscription for %(domain)s failed to "
                         "renew due to: %(error)s." % {
                             'domain': self.domain,
                             'error': e,
                         })
        return True


class ProBonoForm(forms.Form):
    contact_email = forms.EmailField(label=_("Contact email"))
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
