import datetime
import io
import json
import logging
import uuid

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import transaction
from django.forms.fields import (
    BooleanField,
    CharField,
    ChoiceField,
    DateTimeField,
    Field,
    ImageField,
    IntegerField,
    SelectMultiple,
)
from django.forms.widgets import Select
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes, smart_str
from django.utils.functional import cached_property, lazy
from django.utils.http import urlsafe_base64_encode
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop

from captcha.fields import ReCaptchaField
from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.layout import Layout, Submit
from dateutil.relativedelta import relativedelta
from django_countries.data import COUNTRIES
from memoized import memoized
from PIL import Image

from corehq import privileges
from corehq.apps.accounting.exceptions import SubscriptionRenewalError
from corehq.apps.accounting.models import (
    BillingAccount,
    BillingAccountType,
    BillingContactInfo,
    CreditAdjustmentReason,
    CreditLine,
    Currency,
    DefaultProductPlan,
    EntryPoint,
    FeatureType,
    FundingSource,
    PreOrPostPay,
    ProBonoStatus,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionAdjustmentMethod,
    SubscriptionType,
)
from corehq.apps.accounting.utils import (
    cancel_future_subscriptions,
    domain_has_privilege,
    get_account_name_from_default_name,
    is_downgrade,
    log_accounting_error,
)
from corehq.apps.app_manager.const import (
    AMPLIFIES_NO,
    AMPLIFIES_NOT_SET,
    AMPLIFIES_YES,
)
from corehq.apps.app_manager.dbaccessors import (
    get_app,
    get_apps_in_domain,
    get_brief_apps_in_domain,
    get_version_build_id,
)
from corehq.apps.app_manager.exceptions import BuildNotFoundException
from corehq.apps.app_manager.models import (
    Application,
    AppReleaseByLocation,
    LatestEnabledBuildProfiles,
    RemoteApp,
)
from corehq.apps.callcenter.views import (
    CallCenterOptionsController,
    CallCenterOwnerOptionsView,
)
from corehq.apps.domain.auth import get_active_users_by_email
from corehq.apps.domain.extension_points import validate_password_rules
from corehq.apps.domain.models import (
    AREA_CHOICES,
    BUSINESS_UNITS,
    DATA_DICT,
    LOGO_ATTACHMENT,
    RESTRICTED_UCR_EXPRESSIONS,
    SUB_AREA_CHOICES,
    AllowedUCRExpressionSettings,
    AppReleaseModeSetting,
    OperatorCallLimitSettings,
    SMSAccountConfirmationSettings,
    TransferDomainRequest,
    all_restricted_ucr_expressions,
)
from corehq.apps.hqmedia.models import CommCareImage, LogoForSystemEmailsReference
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import DatetimeLocalWidget, HQFormHelper
from corehq.apps.hqwebapp.fields import MultiCharField
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.hqwebapp.widgets import (
    BootstrapCheckboxInput,
    GeoCoderInput,
    Select2Ajax,
)
from corehq.apps.registration.utils import project_logo_emails_context
from corehq.apps.sms.phonenumbers_helper import parse_phone_number
from corehq.apps.users.models import CouchUser, WebUser
from corehq.toggles import (
    EXPORT_HIDE_DELETED_APPLICATIONS,
    HIPAA_COMPLIANCE_CHECKBOX,
    MOBILE_UCR,
    SECURE_SESSION_TIMEOUT,
    TWO_STAGE_USER_PROVISIONING_BY_SMS,
    USE_LOGO_IN_SYSTEM_EMAILS
)
from corehq.util.timezones.fields import TimeZoneField
from corehq.util.timezones.forms import TimeZoneChoiceField

mark_safe_lazy = lazy(mark_safe, str)  # TODO: Use library method


# used to resize uploaded custom logos, aspect ratio is preserved
LOGO_SIZE = (211, 32)

upload_size_limit = f"{settings.MAX_UPLOAD_SIZE_ATTACHMENT/(1024*1024):,.0f}"


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
            inline_label=gettext_lazy("Override project's timezone setting just for me.")
        )
    )
    user_timezone = TimeZoneChoiceField(
        label="My Timezone",
        initial=global_timezone.initial
    )

    def __init__(self, *args, **kwargs):
        super(ProjectSettingsForm, self).__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper(self)
        self.helper.form_id = 'my-project-settings-form'
        self.helper.all().wrap_together(crispy.Fieldset, _('My Timezone'))
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('My Timezone'),
                crispy.Field('global_timezone', css_class='input-xlarge'),
                twbscrispy.PrependedText(
                    'override_global_tz',
                    '',
                    id='override_global_tz',
                    data_bind='checked: override_tz, event: {change: updateForm}'
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
                    css_class='btn-primary',
                    data_bind="disable: disableUpdateSettings"
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


class TransferDomainFormErrors(object):
    USER_DNE = gettext_lazy('The user being transferred to does not exist')
    DOMAIN_MISMATCH = gettext_lazy('Mismatch in domains when confirming')


class TransferDomainForm(forms.ModelForm):

    class Meta(object):
        model = TransferDomainRequest
        fields = ['domain', 'to_username']

    def __init__(self, domain, from_username, *args, **kwargs):
        super(TransferDomainForm, self).__init__(*args, **kwargs)
        self.current_domain = domain
        self.from_username = from_username

        self.fields['domain'].label = _('Type the name of the project to confirm')
        self.fields['to_username'].label = _('New owner\'s CommCare username')

        self.helper = hqcrispy.HQFormHelper()
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
        web_user = WebUser.get_by_username(username)
        if not (web_user and web_user.is_active):
            raise forms.ValidationError(TransferDomainFormErrors.USER_DNE)

        return username


class SubAreaMixin(object):

    def clean_sub_area(self):
        area = self.cleaned_data['area']
        sub_area = self.cleaned_data['sub_area']

        if sub_area:
            if not area:
                raise forms.ValidationError(_('You may not specify a sub area when the project has no specified '
                                              'area'))
        else:
            return None

        sub_areas = []
        for a in DATA_DICT["area"]:
            if a["name"] == area:
                sub_areas = a["sub_areas"]

        if sub_area not in sub_areas:
            raise forms.ValidationError(_('This is not a valid sub-area for the area %s') % area)
        return sub_area


USE_LOCATION_CHOICE = "user_location"
USE_PARENT_LOCATION_CHOICE = 'user_parent_location'


class CallCenterOwnerWidget(Select2Ajax):

    def set_domain(self, domain):
        self.domain = domain

    def render(self, name, value, attrs=None, renderer=None):
        value_to_render = CallCenterOptionsController.convert_owner_id_to_select_choice(value, self.domain)
        return super(CallCenterOwnerWidget, self).render(name, value_to_render, attrs=attrs, renderer=renderer)


class DomainGlobalSettingsForm(forms.Form):
    LOCATION_CHOICES = [USE_LOCATION_CHOICE, USE_PARENT_LOCATION_CHOICE]
    CASES_AND_FIXTURES_CHOICE = "cases_and_fixtures"
    CASES_ONLY_CHOICE = "cases_only"

    hr_name = forms.CharField(
        label=gettext_lazy("Project Name"),
        help_text=gettext_lazy("This name will appear in the upper right corner "
                               "when you are in this project. Changing this name "
                               "will not change the URL of the project.")
    )
    project_description = forms.CharField(
        label=gettext_lazy("Project Description"),
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
        required=False,
        max_length=1000,
        help_text=gettext_lazy(
            "Please provide a short description of your project (Max 1000 characters)."
        )
    )
    default_timezone = TimeZoneChoiceField(label=gettext_noop("Default Timezone"), initial="UTC")

    default_geocoder_location = Field(
        widget=GeoCoderInput(attrs={'placeholder': gettext_lazy('Select a location')}),
        label=gettext_noop("Default project location"),
        required=False,
        help_text=gettext_lazy("Please select your project's default location.")
    )

    logo = ImageField(
        label=gettext_lazy("Custom Logo"),
        required=False,
        help_text=gettext_lazy(
            "Upload a custom image to display instead of the "
            "CommCare HQ logo.  It will be automatically resized to "
            "a height of 32 pixels. Upload size limit is {size_limit} MB."
        ).format(size_limit=upload_size_limit)
    )
    delete_logo = BooleanField(
        label=gettext_lazy("Delete Logo"),
        required=False,
        help_text=gettext_lazy("Delete your custom logo and use the standard one.")
    )
    logo_for_system_emails = ImageField(
        label=gettext_lazy("Logo to use in systems emails"),
        required=False,
        help_text=gettext_lazy(
            "Upload an image to display in system emails from CommCare. It will be displayed in a square format. "
            "The upload size limit is {size_limit} MB."
        ).format(size_limit=upload_size_limit)
    )
    call_center_enabled = BooleanField(
        label=gettext_lazy("Call Center Application"),
        required=False,
        help_text=gettext_lazy("Call Center mode is a CommCare HQ module for managing "
                    "call center workflows. It is still under "
                    "active development. Do not enable for your domain unless "
                    "you're actively piloting it.")
    )
    call_center_type = ChoiceField(
        label=gettext_lazy("Call Center Type"),
        initial=CASES_AND_FIXTURES_CHOICE,
        choices=[
            (CASES_AND_FIXTURES_CHOICE, "Create cases and indicators"),
            (CASES_ONLY_CHOICE, "Create just cases"),
        ],
        help_text=gettext_lazy(
            """
            If "Create cases and indicators" is selected, each user will have a case associated with it,
            and fixtures will be synced containing indicators about each user. If "Create just cases"
            is selected, the fixtures will not be created.
            """
        ),
        required=False,
    )
    call_center_case_owner = Field(
        widget=CallCenterOwnerWidget(attrs={'placeholder': gettext_lazy('Select an Owner...')}),
        label=gettext_lazy("Call Center Case Owner"),
        required=False,
        help_text=gettext_lazy("Select the person who will be listed as the owner "
                    "of all cases created for call center users.")
    )
    call_center_case_type = CharField(
        label=gettext_lazy("Call Center Case Type"),
        required=False,
        help_text=gettext_lazy("Enter the case type to be used for FLWs in call center apps")
    )

    mobile_ucr_sync_interval = IntegerField(
        label=gettext_lazy("Default mobile report sync delay (hours)"),
        required=False,
        help_text=gettext_lazy(
            """
            Default time to wait between sending updated mobile report data to users.
            Can be overridden on a per user basis.
            """
        )
    )

    confirmation_link_expiry = IntegerField(
        label=gettext_lazy("Account confirmation link expiry"),
        required=True,
        help_text=gettext_lazy(
            """
            Default time (in days) for which account confirmation link will be valid.
            """
        )
    )

    operator_call_limit = IntegerField(
        label=gettext_lazy("Call limit"),
        required=True,
        help_text=gettext_lazy(
            """
            Limit on number of calls allowed to an operator for each call type.
            """
        )
    )

    confirmation_sms_project_name = CharField(
        label=gettext_lazy("Confirmation SMS project name"),
        required=True,
        help_text=gettext_lazy("Name of the project to be used in SMS sent for account confirmation to users.")
    )

    release_mode_visibility = BooleanField(
        label=gettext_lazy("Enable Release Mode"),
        required=False,
        help_text=gettext_lazy(
            """
            Check this box to enable release mode setting on the app release page.
            Enabled setting restricts user to directly mark a version 'released'
            and allows users to do so only when they are in 'Release Mode' on the
            release page of applications.
            """
        )
    )

    orphan_case_alerts_warning = BooleanField(
        label=gettext_lazy("Show Orphan Case Alerts on Mobile Worker Edit Page"),
        required=False,
        help_text=gettext_lazy(
            """
            Displays a warning message on the mobile worker location edit page
            about locations that owns cases and only have one assigned mobile worker.
            This helps prevent situations where cases are being orphaned by moving
            the only assigned mobile worker out of the location owning that cases.
            """
        )
    )

    show_deleted_apps_exports = BooleanField(
        label=gettext_lazy("Show deleted apps when creating exports"),
        required=False,
        help_text=gettext_lazy(
            """
            Shows deleted apps under "Unknown Applications" when creating exports
            """
        )
    )

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('domain', None)
        self.domain = self.project.name
        self.can_use_custom_logo = kwargs.pop('can_use_custom_logo', False)
        super(DomainGlobalSettingsForm, self).__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper(self)
        self.helper[5] = twbscrispy.PrependedText('delete_logo', '')
        self.helper[7] = twbscrispy.PrependedText('call_center_enabled', '')
        self.helper[15] = twbscrispy.PrependedText('release_mode_visibility', '')
        self.helper[16] = twbscrispy.PrependedText('orphan_case_alerts_warning', '')
        self.helper[17] = twbscrispy.PrependedText('show_deleted_apps_exports', '')
        self.helper.all().wrap_together(crispy.Fieldset, _('Edit Basic Information'))
        self.helper.layout.append(
            hqcrispy.FormActions(
                StrictButton(
                    _("Update Basic Info"),
                    type="submit",
                    css_class='btn-primary',
                )
            )
        )
        self.fields['default_timezone'].label = gettext_lazy('Default timezone')

        if not self.can_use_custom_logo:
            del self.fields['logo']
            del self.fields['delete_logo']
        self.system_emails_logo_enabled = USE_LOGO_IN_SYSTEM_EMAILS.enabled(self.domain)
        if not self.system_emails_logo_enabled:
            del self.fields['logo_for_system_emails']

        if self.project:
            if not self.project.call_center_config.enabled:
                del self.fields['call_center_enabled']
                del self.fields['call_center_type']
                del self.fields['call_center_case_owner']
                del self.fields['call_center_case_type']
            else:
                owner_field = self.fields['call_center_case_owner']
                owner_field.widget.set_url(
                    reverse(CallCenterOwnerOptionsView.url_name, args=(self.domain,))
                )
                owner_field.widget.set_domain(self.domain)

        if not MOBILE_UCR.enabled(self.domain):
            del self.fields['mobile_ucr_sync_interval']

        self._handle_call_limit_visibility()
        self._handle_account_confirmation_by_sms_settings()
        self._handle_release_mode_setting_value()
        self._handle_orphan_case_alerts_setting_value()

        if not EXPORT_HIDE_DELETED_APPLICATIONS.enabled(self.domain):
            del self.fields['show_deleted_apps_exports']
        else:
            self._handle_show_deleted_apps_exports_setting_value()


    def _handle_account_confirmation_by_sms_settings(self):
        if not TWO_STAGE_USER_PROVISIONING_BY_SMS.enabled(self.domain):
            del self.fields['confirmation_link_expiry']
            del self.fields['confirmation_sms_project_name']
        else:
            settings_obj = SMSAccountConfirmationSettings.get_settings(self.domain)
            min_value_expiry = SMSAccountConfirmationSettings.CONFIRMATION_LINK_EXPIRY_DAYS_MINIMUM
            max_value_expiry = SMSAccountConfirmationSettings.CONFIRMATION_LINK_EXPIRY_DAYS_MAXIMUM
            self.fields['confirmation_link_expiry'].initial = settings_obj.confirmation_link_expiry_time
            self._add_range_validation_to_integer_input(
                "confirmation_link_expiry", min_value_expiry, max_value_expiry
            )
            project_max_length = SMSAccountConfirmationSettings.PROJECT_NAME_MAX_LENGTH
            self.fields['confirmation_sms_project_name'].initial = settings_obj.project_name
            self.fields['confirmation_sms_project_name'].max_length = project_max_length

    def _handle_call_limit_visibility(self):
        if self.domain not in OperatorCallLimitSettings.objects.values_list('domain', flat=True):
            del self.fields['operator_call_limit']
            return
        existing_limit_setting = OperatorCallLimitSettings.objects.get(domain=self.domain)
        self.fields['operator_call_limit'].initial = existing_limit_setting.call_limit
        self._add_range_validation_to_integer_input(
            "operator_call_limit", OperatorCallLimitSettings.CALL_LIMIT_MINIMUM,
            OperatorCallLimitSettings.CALL_LIMIT_MAXIMUM
        )

    def _handle_release_mode_setting_value(self):
        self.fields['release_mode_visibility'].initial = AppReleaseModeSetting.get_settings(
            domain=self.domain).is_visible

    def _handle_orphan_case_alerts_setting_value(self):
        self.fields['orphan_case_alerts_warning'].initial = self.project.orphan_case_alerts_warning

    def _handle_show_deleted_apps_exports_setting_value(self):
        self.fields['show_deleted_apps_exports'].initial = self.project.show_deleted_apps_exports

    def _add_range_validation_to_integer_input(self, settings_name, min_value, max_value):
        setting = self.fields.get(settings_name)
        min_validator = MinValueValidator(min_value)
        max_validator = MaxValueValidator(max_value)
        setting.validators.extend([min_validator, max_validator])

    def clean_default_timezone(self):
        data = self.cleaned_data['default_timezone']
        timezone_field = TimeZoneField()
        timezone_field.run_validators(data)
        return smart_str(data)

    def clean_default_geocoder_location(self):
        data = self.cleaned_data.get('default_geocoder_location')
        if isinstance(data, dict):
            return data
        return json.loads(data or '{}')

    def _clean_image(self, field_name, permission, error_message):
        image = self.cleaned_data[field_name]
        if permission and image:
            if image.size > settings.MAX_UPLOAD_SIZE_ATTACHMENT:
                raise ValidationError(
                    _(error_message)
                )
        return image

    def clean_logo(self):
        return self._clean_image(
            'logo',
            self.can_use_custom_logo,
            _("Logo exceeds {} MB size limit").format(upload_size_limit)
        )

    def clean_logo_for_system_emails(self):
        return self._clean_image(
            'logo_for_system_emails',
            self.system_emails_logo_enabled,
            _("Logo for systems emails exceeds {} MB size limit").format(upload_size_limit)
        )

    def clean_confirmation_link_expiry(self):
        data = self.cleaned_data['confirmation_link_expiry']
        return DomainGlobalSettingsForm.validate_integer_value(data, "Confirmation link expiry")

    def clean_operator_call_limit(self):
        data = self.cleaned_data['operator_call_limit']
        return DomainGlobalSettingsForm.validate_integer_value(data, "Operator call limit")

    def clean_release_mode_visibility(self):
        data = self.cleaned_data['release_mode_visibility']
        if data not in [True, False]:
            raise forms.ValidationError(_("Release Mode Visibility should be a boolean."))
        return data

    @staticmethod
    def validate_integer_value(value, value_name):
        try:
            return int(value)
        except ValueError:
            raise forms.ValidationError(_("{} should be an integer.").format(value_name))

    def clean(self):
        cleaned_data = super(DomainGlobalSettingsForm, self).clean()
        if (cleaned_data.get('call_center_enabled')
            and (not cleaned_data.get('call_center_case_type')
                 or not cleaned_data.get('call_center_case_owner')
                 or not cleaned_data.get('call_center_type'))):
            raise forms.ValidationError(_(
                'You must choose a Call Center Type, Owner, and Case Type to use the call center application. '
                'Please uncheck the "Call Center Application" setting or enter values for the other fields.'
            ))

        return cleaned_data

    def _save_logo_configuration(self, domain):
        """
        :raises IOError: if unable to save (e.g. PIL is unable to save PNG in CMYK mode)
        """
        if self.can_use_custom_logo:
            logo = self.cleaned_data['logo']
            if logo:

                input_image = Image.open(io.BytesIO(logo.read()))
                input_image.load()
                input_image.thumbnail(LOGO_SIZE)
                # had issues trying to use a BytesIO instead
                tmpfilename = "/tmp/%s_%s" % (uuid.uuid4(), logo.name)
                input_image.save(tmpfilename, 'PNG')

                with open(tmpfilename, 'rb') as tmpfile:
                    domain.put_attachment(tmpfile, name=LOGO_ATTACHMENT)
            elif self.cleaned_data['delete_logo']:
                domain.delete_attachment(LOGO_ATTACHMENT)

    def _save_logo_for_system_emails(self, domain_obj):
        logo = self.cleaned_data['logo_for_system_emails']
        if logo:
            image_data = logo.read()
            image = CommCareImage.get_by_data(image_data)
            image.attach_data(image_data, original_filename='logo_for_systems_emails.png')
            image.add_domain(domain_obj.name)
            image.save()
            ref, created = LogoForSystemEmailsReference.objects.get_or_create(domain=domain_obj.name)
            ref.image_id = image._id
            ref.save()

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
                cc_config.user_location_ancestor_level = 1 if owner == USE_PARENT_LOCATION_CHOICE else 0
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

    def _save_account_confirmation_settings(self, domain):
        if TWO_STAGE_USER_PROVISIONING_BY_SMS.enabled(domain.name):
            settings = SMSAccountConfirmationSettings.get_settings(domain.name)
            settings.project_name = self.cleaned_data.get('confirmation_sms_project_name')
            settings.confirmation_link_expiry_time = self.cleaned_data.get('confirmation_link_expiry')
            settings.save()

    def _save_release_mode_setting(self, domain):
        setting_obj = AppReleaseModeSetting.get_settings(domain=domain.name)
        if self.cleaned_data.get("release_mode_visibility") != setting_obj.is_visible:
            setting_obj.is_visible = self.cleaned_data.get("release_mode_visibility")
            setting_obj.save()

    def _save_orphan_case_alerts_setting(self, domain):
        domain.orphan_case_alerts_warning = self.cleaned_data.get("orphan_case_alerts_warning", False)

    def _save_show_deleted_apps_exports(self, domain):
        domain.show_deleted_apps_exports = self.cleaned_data.get("show_deleted_apps_exports", True)

    def save(self, request, domain):
        domain.hr_name = self.cleaned_data['hr_name']
        domain.project_description = self.cleaned_data['project_description']
        domain.default_mobile_ucr_sync_interval = self.cleaned_data.get('mobile_ucr_sync_interval', None)
        domain.default_geocoder_location = self.cleaned_data.get('default_geocoder_location')
        if self.cleaned_data.get("operator_call_limit"):
            setting_obj = OperatorCallLimitSettings.objects.get(domain=self.domain)
            setting_obj.call_limit = self.cleaned_data.get("operator_call_limit")
            setting_obj.save()
        try:
            self._save_logo_configuration(domain)
            if self.system_emails_logo_enabled:
                self._save_logo_for_system_emails(domain)
        except IOError as err:
            messages.error(request, _('Unable to save logo: {}').format(err))
        self._save_call_center_configuration(domain)
        self._save_timezone_configuration(domain)
        self._save_account_confirmation_settings(domain)
        self._save_release_mode_setting(domain)
        self._save_orphan_case_alerts_setting(domain)
        if EXPORT_HIDE_DELETED_APPLICATIONS.enabled(self.domain):
            self._save_show_deleted_apps_exports(domain)
        domain.save()
        return True


class DomainMetadataForm(DomainGlobalSettingsForm):

    cloudcare_releases = ChoiceField(
        label=gettext_lazy("Web Apps should use"),
        initial=None,
        required=False,
        choices=(
            ('stars', gettext_lazy('Latest starred version')),
            ('nostars', gettext_lazy('Highest numbered version (not recommended)')),
        ),
        help_text=gettext_lazy("Choose whether Web Apps should use the latest starred build or highest numbered "
                               "build in your application.")
    )

    def __init__(self, *args, **kwargs):
        super(DomainMetadataForm, self).__init__(*args, **kwargs)

        if self.project.cloudcare_releases == 'default' \
                or not domain_has_privilege(self.domain, privileges.CLOUDCARE):
            # if the cloudcare_releases flag was just defaulted, don't bother showing
            # this setting at all
            del self.fields['cloudcare_releases']
        if not domain_has_privilege(self.domain, privileges.GEOCODER):
            del self.fields['default_geocoder_location']

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
        except Exception as e:
            logging.exception("couldn't save project settings - error is %s" % e)
            return False


def tuple_of_copies(a_list, blank=True):
    ret = [(item, item) for item in a_list]
    if blank:
        ret.insert(0, ('', '---'))
    return tuple(ret)


class PrivacySecurityForm(forms.Form):
    restrict_superusers = BooleanField(
        label=gettext_lazy("Restrict Dimagi Staff Access"),
        required=False,
        help_text=gettext_lazy(
            "CommCare support staff sometimes require access "
            "to your project space to provide rapid, in-depth support. "
            "Checking this box will restrict the degree of support they "
            "will be able to provide in the event that you report an issue. "
            "You may also miss out on important communications and updates. "
            "Regardless of whether this option is checked, "
            "Commcare support staff will have access "
            "to your billing information and project metadata; "
            "and CommCare system administrators will also have direct access "
            "to data infrastructure strictly for the purposes of system administration "
            "as outlined in our "
            '<a href="https://www.dimagi.com/terms/latest/privacy/">Privacy Policy</a>.'
        )
    )
    secure_submissions = BooleanField(
        label=gettext_lazy("Secure submissions"),
        required=False,
        help_text=mark_safe_lazy(gettext_lazy(  # nosec: no user input
            "Secure Submissions prevents others from impersonating your mobile workers. "
            "This setting requires all deployed applications to be using secure "
            "submissions as well. "
            "<a href='https://help.commcarehq.org/display/commcarepublic/Project+Space+Settings'>"
            "Read more about secure submissions here</a>"))
    )
    secure_sessions = BooleanField(
        label=gettext_lazy("Shorten Inactivity Timeout"),
        required=False,
        help_text=gettext_lazy("All web users on this project will be logged out after {} minutes "
                               "of inactivity").format(settings.SECURE_TIMEOUT)
    )
    secure_sessions_timeout = IntegerField(
        label=gettext_lazy("Inactivity Timeout Length"),
        required=False,
        help_text=gettext_lazy("Override the default {}-minute length of the inactivity timeout. Has no effect "
                               "unless inactivity timeout is on. Note that when this is updated, users may need "
                               "to log out and back in for it to take effect.").format(settings.SECURE_TIMEOUT)
    )
    allow_domain_requests = BooleanField(
        label=gettext_lazy("Web user requests"),
        required=False,
        help_text=gettext_lazy("Allow unknown users to request web access to the domain."),
    )
    hipaa_compliant = BooleanField(
        label=gettext_lazy("HIPAA compliant"),
        required=False,
    )
    two_factor_auth = BooleanField(
        label=gettext_lazy("Two Factor Authentication"),
        required=False,
        help_text=gettext_lazy("All users on this project will be required to enable two factor authentication")
    )
    strong_mobile_passwords = BooleanField(
        label=gettext_lazy("Require Strong Passwords for Mobile Workers"),
        required=False,
        help_text=gettext_lazy("All mobile workers in this project will be required to have a strong password")
    )
    ga_opt_out = BooleanField(
        label=gettext_lazy("Disable Google Analytics"),
        required=False,
    )
    disable_mobile_login_lockout = BooleanField(
        label=gettext_lazy("Disable Mobile Worker Lockout"),
        required=False,
        help_text=gettext_lazy("Mobile Workers will never be locked out of their account, regardless"
            "of the number of failed attempts")
    )
    allow_invite_email_only = BooleanField(
        label=gettext_lazy("During sign up, only allow the email address the invitation was sent to"),
        required=False,
        help_text=gettext_lazy("Disables the email field on the sign up page")
    )

    def __init__(self, *args, **kwargs):
        user_name = kwargs.pop('user_name')
        domain = kwargs.pop('domain')
        super(PrivacySecurityForm, self).__init__(*args, **kwargs)

        excluded_fields = []
        if not domain_has_privilege(domain, privileges.ADVANCED_DOMAIN_SECURITY):
            excluded_fields.append('ga_opt_out')
            excluded_fields.append('strong_mobile_passwords')
            excluded_fields.append('two_factor_auth')
            excluded_fields.append('secure_sessions')
        if not HIPAA_COMPLIANCE_CHECKBOX.enabled(user_name):
            excluded_fields.append('hipaa_compliant')
        if not SECURE_SESSION_TIMEOUT.enabled(domain):
            excluded_fields.append('secure_sessions_timeout')

        # PrependedText ensures the label is to the left of the checkbox, and the help text beneath.
        # Feels like there should be a better way to apply these styles, as we aren't pre-pending anything
        fields = [twbscrispy.PrependedText(field_name, '')
            for field_name in self.fields.keys() if field_name not in excluded_fields]

        self.helper = hqcrispy.HQFormHelper(self)
        self.helper.layout = Layout(
            crispy.Fieldset(
                _('Edit Privacy Settings'),
                *fields
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _('Update Privacy Settings'),
                    type='submit',
                    css_class='btn-primary'
                )
            )
        )

    def save(self, domain_obj):
        domain_obj.restrict_superusers = self.cleaned_data.get('restrict_superusers', False)
        domain_obj.allow_domain_requests = self.cleaned_data.get('allow_domain_requests', False)
        domain_obj.secure_sessions = self.cleaned_data.get('secure_sessions', False)
        domain_obj.secure_sessions_timeout = self.cleaned_data.get('secure_sessions_timeout', None)
        domain_obj.two_factor_auth = self.cleaned_data.get('two_factor_auth', False)

        domain_obj.strong_mobile_passwords = self.cleaned_data.get('strong_mobile_passwords', False)
        secure_submissions = self.cleaned_data.get(
            'secure_submissions', False)
        apps_to_save = []
        if secure_submissions != domain_obj.secure_submissions:
            for app in get_apps_in_domain(domain_obj.name):
                if app.secure_submissions != secure_submissions:
                    app.secure_submissions = secure_submissions
                    apps_to_save.append(app)
        domain_obj.secure_submissions = secure_submissions
        domain_obj.hipaa_compliant = self.cleaned_data.get('hipaa_compliant', False)
        domain_obj.ga_opt_out = self.cleaned_data.get('ga_opt_out', False)
        domain_obj.disable_mobile_login_lockout = self.cleaned_data.get('disable_mobile_login_lockout', False)
        domain_obj.allow_invite_email_only = self.cleaned_data.get('allow_invite_email_only', False)

        domain_obj.save()

        if apps_to_save:
            apps = [app for app in apps_to_save if isinstance(app, Application)]
            remote_apps = [app for app in apps_to_save if isinstance(app, RemoteApp)]
            if apps:
                Application.bulk_save(apps)
            if remote_apps:
                RemoteApp.bulk_save(remote_apps)

        return True


class DomainInternalForm(forms.Form, SubAreaMixin):
    sf_contract_id = CharField(label="Salesforce Contract ID", required=False)
    sf_account_id = CharField(label="Salesforce Account ID", required=False)
    initiative = forms.MultipleChoiceField(label="Initiative",
                                           widget=forms.CheckboxSelectMultiple(),
                                           choices=tuple_of_copies(DATA_DICT["initiatives"], blank=False),
                                           required=False)
    workshop_region = CharField(
        label="Workshop Region",
        required=False,
        help_text="e.g. US, LAC, SA, Sub-Saharan Africa, Southeast Asia, etc.")
    self_started = ChoiceField(
        label="Self Started?",
        choices=tf_choices('Yes', 'No'),
        required=False,
        help_text=(
            "The organization built and deployed their app themselves. Dimagi may have provided indirect support"
        ))
    is_test = ChoiceField(
        label="Real Project",
        choices=(('none', 'Unknown'),
                 ('true', 'Test'),
                 ('false', 'Real'),)
    )
    area = ChoiceField(
        label="Sector*",
        required=False,
        choices=tuple_of_copies(AREA_CHOICES))
    sub_area = ChoiceField(
        label="Sub-Sector*",
        required=False,
        choices=tuple_of_copies(SUB_AREA_CHOICES))
    organization_name = CharField(
        label="Organization Name*",
        required=False,
        help_text="Quick 1-2 sentence summary of the project.",
    )
    notes = CharField(label="Notes*", required=False, widget=forms.Textarea(attrs={"class": "vertical-resize"}))
    phone_model = CharField(
        label="Device Model",
        help_text="Add Web Apps, if this project is using Web Apps as well",
        required=False,
    )
    business_unit = forms.ChoiceField(
        label='Business Unit',
        choices=tuple_of_copies(BUSINESS_UNITS),
        required=False,
    )
    countries = forms.MultipleChoiceField(
        label="Countries",
        choices=sorted(list(COUNTRIES.items()), key=lambda x: x[0]),
        required=False,
    )
    commtrack_domain = ChoiceField(
        label="CommCare Supply Project",
        choices=tf_choices('Yes', 'No'),
        required=False,
        help_text="This app aims to improve the supply of goods and materials"
    )
    performance_threshold = IntegerField(
        label="Performance Threshold",
        required=False,
        help_text=(
            'The number of forms submitted per month for a user to count as "performing well". '
            'The default value is 15.'
        )
    )
    experienced_threshold = IntegerField(
        label="Experienced Threshold",
        required=False,
        help_text=(
            "The number of different months in which a worker must submit forms to count as experienced. "
            "The default value is 3."
        )
    )
    amplifies_workers = ChoiceField(
        label="Service Delivery App",
        choices=[(AMPLIFIES_NOT_SET, '* Not Set'), (AMPLIFIES_YES, 'Yes'), (AMPLIFIES_NO, 'No')],
        required=False,
        help_text=("This application is used for service delivery. Examples: An "
                   "FLW who uses CommCare to improve counseling and screening of pregnant women. "
                   "An FLW that uses CommCare Supply to improve their supply of medicines. A teacher "
                   "who uses CommCare to assess and improve students' performance."
                   )
    )
    amplifies_project = ChoiceField(
        label="Amplifies Project",
        choices=[(AMPLIFIES_NOT_SET, '* Not Set'), (AMPLIFIES_YES, 'Yes'), (AMPLIFIES_NO, 'No')],
        required=False,
        help_text=("Amplifies the impact of a Frontline Program (FLP). "
                   "Examples: Programs that use M&E data collected by CommCare. "
                   "Programs that use CommCare data to make programmatic decisions."
                   )
    )
    data_access_threshold = IntegerField(
        label="Minimum Monthly Data Accesses",
        required=False,
        help_text=(
            "Minimum number of times project staff are expected to access CommCare data each month. "
            "The default value is 20."
        )
    )
    partner_technical_competency = IntegerField(
        label="Partner Technical Competency",
        required=False,
        min_value=1,
        max_value=5,
        help_text=(
            "Please rate the technical competency of the partner on a scale from "
            "1 to 5. 1 means low-competency, and we should expect LOTS of basic "
            "hand-holding. 5 means high-competency, so if they report a bug it's "
            "probably a real issue with CommCare HQ or a really good idea."
        ),
    )
    support_prioritization = IntegerField(
        label="Support Prioritization",
        required=False,
        min_value=1,
        max_value=3,
        help_text=(
            "Based on the impact of this project and how good this partner was "
            "to work with, how much would you prioritize support for this "
            'partner? 1 means "Low. Take your time." You might rate a partner '
            '"1" because they\'ve been absolutely terrible to you and low impact. '
            '3 means "High priority. Be nice". You might rate a partner "3" '
            "because even though they can't afford a PRO plan, you know they "
            "are changing the world. Or they are an unusually high priority "
            "strategic partner."
        ),
    )
    gs_continued_involvement = ChoiceField(
        label="GS Continued Involvement",
        choices=[(AMPLIFIES_NOT_SET, '* Not Set'), (AMPLIFIES_YES, 'Yes'), (AMPLIFIES_NO, 'No')],
        required=False,
        help_text=(
            "Do you want to continue to be involved in this project? No, please "
            "only reach out if absolutely necessary. Yes. I want to see what "
            "happens and be kept in the loop."
        ),
    )
    technical_complexity = ChoiceField(
        label="Technical Complexity",
        choices=[(AMPLIFIES_NOT_SET, '* Not Set'), (AMPLIFIES_YES, 'Yes'), (AMPLIFIES_NO, 'No')],
        required=False,
        help_text=(
            "Is this an innovation project involving unusual technology which"
            "we expect will require different support than a typical deployment?"
        ),
    )
    app_design_comments = CharField(
        label="App Design Comments",
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
        required=False,
        help_text=(
            "Unusual workflows or design decisions for others to watch out for."
        ),
    )
    training_materials = CharField(
        label="Training materials",
        required=False,
        help_text=(
            "Where to find training materials or other relevant resources."
        ),
    )
    partner_comments = CharField(
        label="Partner Comments",
        widget=forms.Textarea,
        required=False,
        help_text=(
            "past or anticipated problems with this partner."
        ),
    )
    partner_contact = CharField(
        label="Partner contact",
        required=False,
        help_text=(
            "Primary partner point of contact going forward (type username of existing web user)."
        ),
    )
    dimagi_contact = CharField(
        label="Dimagi contact",
        required=False,
        help_text=(
            "Primary Dimagi point of contact going forward (type username of existing web user)."
        ),
    )
    send_handoff_email = forms.BooleanField(
        label="Send Hand-off Email",
        required=False,
        help_text=(
            "Check this box to trigger a hand-off email to the partner when this form is submitted."
        ),
    )
    use_custom_auto_case_update_hour = forms.ChoiceField(
        label=gettext_lazy("Choose specific time for custom auto case update rules to run"),
        required=True,
        choices=(
            ('N', gettext_lazy("No")),
            ('Y', gettext_lazy("Yes")),
        ),
    )
    auto_case_update_hour = forms.IntegerField(
        label=gettext_lazy("Hour of the day, in UTC, for rules to run (0-23)"),
        required=False,
        min_value=0,
        max_value=23,
    )
    use_custom_auto_case_update_limit = forms.ChoiceField(
        label=gettext_lazy("Set custom auto case update rule limits"),
        required=True,
        choices=(
            ('N', gettext_lazy("No")),
            ('Y', gettext_lazy("Yes")),
        ),
    )
    auto_case_update_limit = forms.IntegerField(
        label=gettext_lazy("Max allowed updates in a daily run"),
        required=False,
        min_value=1000,
    )
    use_custom_odata_feed_limit = forms.ChoiceField(
        label=gettext_lazy("Set custom OData Feed Limit? Default is {}.").format(
            settings.DEFAULT_ODATA_FEED_LIMIT),
        required=True,
        choices=(
            ('N', gettext_lazy("No")),
            ('Y', gettext_lazy("Yes")),
        ),
    )
    odata_feed_limit = forms.IntegerField(
        label=gettext_lazy("Max allowed OData Feeds"),
        required=False,
        min_value=1,
    )
    granted_messaging_access = forms.BooleanField(
        label="Enable Messaging",
        required=False,
        help_text="Check this box to enable messaging.",  # TODO through non-test gateways
    )
    active_ucr_expressions = forms.MultipleChoiceField(
        label="Expressions for SaaS to Manage",
        choices=RESTRICTED_UCR_EXPRESSIONS,
        required=False,
    )

    def __init__(self, domain, can_edit_eula, *args, **kwargs):
        super(DomainInternalForm, self).__init__(*args, **kwargs)
        self.domain = domain
        self.can_edit_eula = can_edit_eula
        additional_fields = []
        if self.can_edit_eula:
            additional_fields = ['custom_eula', 'can_use_data']
            self.fields['custom_eula'] = ChoiceField(
                label="Custom Eula?",
                choices=tf_choices(_('Yes'), _('No')),
                required=False,
                help_text='Set to "yes" if this project has a customized EULA as per their contract.'
            )
            self.fields['can_use_data'] = ChoiceField(
                label="Can use project data?",
                choices=tf_choices('Yes', 'No'),
                required=False,
                help_text='Set to "no" if this project opts out of data usage. Defaults to "yes".'
            )

        self.helper = hqcrispy.HQFormHelper()
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
                'business_unit',
                'countries',
                'commtrack_domain',
                'performance_threshold',
                'experienced_threshold',
                'amplifies_workers',
                'amplifies_project',
                'data_access_threshold',
                crispy.Div(*additional_fields),
            ),
            crispy.Fieldset(
                _("Support Hand-off information"),
                'partner_technical_competency',
                'support_prioritization',
                'gs_continued_involvement',
                'technical_complexity',
                'app_design_comments',
                'training_materials',
                'partner_comments',
                'partner_contact',
                'send_handoff_email',
                'dimagi_contact',
            ),
            crispy.Fieldset(
                _("Project Limits"),
                crispy.Field(
                    'use_custom_auto_case_update_limit',
                    data_bind='value: use_custom_auto_case_update_limit',
                ),
                crispy.Div(
                    crispy.Field('auto_case_update_limit'),
                    data_bind="visible: use_custom_auto_case_update_limit() === 'Y'",
                ),
                crispy.Field(
                    'use_custom_auto_case_update_hour',
                    data_bind='value: use_custom_auto_case_update_hour',
                ),
                crispy.Div(
                    crispy.Field('auto_case_update_hour'),
                    data_bind="visible: use_custom_auto_case_update_hour() === 'Y'",
                ),
                crispy.Field(
                    'use_custom_odata_feed_limit',
                    data_bind="value: use_custom_odata_feed_limit",
                ),
                crispy.Div(
                    crispy.Field('odata_feed_limit'),
                    data_bind="visible: use_custom_odata_feed_limit() === 'Y'",
                ),
                'granted_messaging_access',
                'active_ucr_expressions',
            ),
            crispy.Fieldset(
                _("Salesforce Details"),
                'sf_contract_id',
                'sf_account_id',
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _("Update Project Information"),
                    type="submit",
                    css_class='btn-primary',
                ),
            ),
        )

    @property
    def current_values(self):
        return {
            'use_custom_auto_case_update_hour': self['use_custom_auto_case_update_hour'].value(),
            'use_custom_auto_case_update_limit': self['use_custom_auto_case_update_limit'].value(),
            'use_custom_odata_feed_limit': self['use_custom_odata_feed_limit'].value()
        }

    def _get_user_or_fail(self, field):
        username = self.cleaned_data[field]
        if not username:
            return None
        user = WebUser.get_by_username(username)
        if not user:
            msg = "Web user with username '{username}' does not exist"
            self.add_error(field, msg.format(username=username))
        elif not user.is_member_of(self.domain):
            msg = "'{username}' is not the username of a web user in '{domain}'"
            self.add_error(field, msg.format(username=username, domain=self.domain))
        return user

    def clean_active_ucr_expressions(self):
        value = self.cleaned_data.get('active_ucr_expressions')
        all_expressions = all_restricted_ucr_expressions()
        for expr in value:
            if expr not in all_expressions:
                raise forms.ValidationError(_(f"Unknown expression {expr}"))
        return value

    def clean_auto_case_update_hour(self):
        if self.cleaned_data.get('use_custom_auto_case_update_hour') != 'Y':
            return None

        value = self.cleaned_data.get('auto_case_update_hour')
        if not value:
            raise forms.ValidationError(_("This field is required"))

        return value

    def clean_auto_case_update_limit(self):
        if self.cleaned_data.get('use_custom_auto_case_update_limit') != 'Y':
            return None

        value = self.cleaned_data.get('auto_case_update_limit')
        if not value:
            raise forms.ValidationError(_("This field is required"))

        return value

    def clean_odata_feed_limit(self):
        if self.cleaned_data.get('use_custom_odata_feed_limit') != 'Y':
            return None

        value = self.cleaned_data.get('odata_feed_limit')
        if not value:
            raise forms.ValidationError(_("Please specify a limit for OData feeds."))

        return value

    def clean(self):
        send_handoff_email = self.cleaned_data['send_handoff_email']

        partner_user = self._get_user_or_fail('partner_contact')
        if not partner_user and send_handoff_email:
            msg = "You can't send a hand-off email without specifying a partner contact."
            self.add_error('partner_contact', msg)

        dimagi_user = self._get_user_or_fail('dimagi_contact')
        if send_handoff_email and not dimagi_user:
            msg = "You can't send a hand-off email without specifying a contact at dimagi."
            self.add_error('dimagi_contact', msg)
        elif send_handoff_email and not dimagi_user.full_name:
            msg = ("The dimagi user '{}' does not have a name configured, please"
                   "go to your account settings and add a name before attempting "
                   "to send an email to the partner.").format(dimagi_user.username)
            self.add_error('dimagi_contact', msg)

    def save(self, domain):
        kwargs = {
            "workshop_region": self.cleaned_data["workshop_region"]
        } if self.cleaned_data["workshop_region"] else {}
        if self.can_edit_eula:
            kwargs['custom_eula'] = self.cleaned_data['custom_eula'] == 'true'
            kwargs['can_use_data'] = self.cleaned_data['can_use_data'] == 'true'

        domain.update_deployment(
            countries=self.cleaned_data['countries'],
        )
        ucr_expressions = self.cleaned_data['active_ucr_expressions']
        AllowedUCRExpressionSettings.save_allowed_ucr_expressions(domain.name, ucr_expressions)
        domain.is_test = self.cleaned_data['is_test']
        domain.auto_case_update_hour = self.cleaned_data['auto_case_update_hour']
        domain.auto_case_update_limit = self.cleaned_data['auto_case_update_limit']
        domain.odata_feed_limit = self.cleaned_data['odata_feed_limit']
        domain.granted_messaging_access = self.cleaned_data['granted_messaging_access']
        domain.update_internal(
            sf_contract_id=self.cleaned_data['sf_contract_id'],
            sf_account_id=self.cleaned_data['sf_account_id'],
            initiative=self.cleaned_data['initiative'],
            self_started=self.cleaned_data['self_started'] == 'true',
            area=self.cleaned_data['area'],
            sub_area=self.cleaned_data['sub_area'],
            organization_name=self.cleaned_data['organization_name'],
            notes=self.cleaned_data['notes'],
            phone_model=self.cleaned_data['phone_model'],
            commtrack_domain=self.cleaned_data['commtrack_domain'] == 'true',
            performance_threshold=self.cleaned_data['performance_threshold'],
            experienced_threshold=self.cleaned_data['experienced_threshold'],
            amplifies_workers=self.cleaned_data['amplifies_workers'],
            amplifies_project=self.cleaned_data['amplifies_project'],
            business_unit=self.cleaned_data['business_unit'],
            data_access_threshold=self.cleaned_data['data_access_threshold'],
            partner_technical_competency=self.cleaned_data['partner_technical_competency'],
            support_prioritization=self.cleaned_data['support_prioritization'],
            gs_continued_involvement=self.cleaned_data['gs_continued_involvement'],
            technical_complexity=self.cleaned_data['technical_complexity'],
            app_design_comments=self.cleaned_data['app_design_comments'],
            training_materials=self.cleaned_data['training_materials'],
            partner_comments=self.cleaned_data['partner_comments'],
            partner_contact=self.cleaned_data['partner_contact'],
            dimagi_contact=self.cleaned_data['dimagi_contact'],
            **kwargs
        )


def clean_password(txt):
    message = validate_password_rules(txt)
    if message:
        raise forms.ValidationError(message)
    return txt


class NoAutocompleteMixin(object):

    def __init__(self, *args, **kwargs):
        super(NoAutocompleteMixin, self).__init__(*args, **kwargs)
        if settings.DISABLE_AUTOCOMPLETE_ON_SENSITIVE_FORMS:
            for field in self.fields.values():
                field.widget.attrs.update({'autocomplete': 'off'})


class HQPasswordResetForm(NoAutocompleteMixin, forms.Form):
    """
    Only finds users and emails forms where the USERNAME is equal to the
    email specified (preventing Mobile Workers from using this form to submit).

    This small change is why we can't use the default PasswordReset form.
    """
    email = forms.EmailField(label=gettext_lazy("Email"), max_length=254,
                             widget=forms.TextInput(attrs={'class': 'form-control'}))
    if settings.RECAPTCHA_PRIVATE_KEY:
        captcha = ReCaptchaField(label="")
    error_messages = {
        'unknown': gettext_lazy("That email address doesn't have an associated user account. Are you sure you've "
                                "registered?"),
        'unusable': gettext_lazy("The user account associated with this email address cannot reset the "
                                 "password."),
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
             from_email=None, request=None, **kwargs):
        """
        Generates a one-use only link for resetting password and sends to the
        user.
        """

        if settings.IS_SAAS_ENVIRONMENT:
            subject_template_name = 'registration/email/password_reset_subject_hq.txt'
            email_template_name = 'registration/email/password_reset_email_hq.html'

        email = self.cleaned_data["email"]

        # this is the line that we couldn't easily override in PasswordForm where
        # we specifically filter for the username, not the email, so that
        # mobile workers who have the same email set as a web worker don't
        # get a password reset email.
        active_users = get_active_users_by_email(email)

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

            couch_user = CouchUser.from_django_user(user)
            if not couch_user:
                continue

            user_email = couch_user.get_email()
            if not user_email:
                continue

            c = {
                'email': user_email,
                'domain': domain,
                'site_name': site_name,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'user': user,
                'token': token_generator.make_token(user),
                'protocol': 'https' if use_https else 'http',
            }
            c.update(project_logo_emails_context(None, couch_user=couch_user))
            subject = render_to_string(subject_template_name, c)
            # Email subject *must not* contain newlines
            subject = ''.join(subject.splitlines())

            message_plaintext = render_to_string('registration/password_reset_email.html', c)
            message_html = render_to_string(email_template_name, c)

            send_html_email_async.delay(
                subject, user_email, message_html,
                text_content=message_plaintext,
                email_from=settings.DEFAULT_FROM_EMAIL
            )


class ConfidentialPasswordResetForm(HQPasswordResetForm):

    def clean_email(self):
        try:
            return super(ConfidentialPasswordResetForm, self).clean_email()
        except forms.ValidationError:
            # The base class throws various emails that give away information about the user;
            # we can pretend all is well since the save() method is safe for missing users.
            return self.cleaned_data['email']


class HQSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label=gettext_lazy("New password"),
        widget=forms.PasswordInput(attrs={'data-bind': "value: password, valueUpdate: 'input'"}),
        help_text=mark_safe('<span data-bind="text: passwordHelp, css: color">')  # nosec: no user input
    )

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
        widget=forms.SelectMultiple(choices=[]),
    )

    class Meta(object):
        model = BillingContactInfo
        fields = ['first_name', 'last_name', 'phone_number', 'company_name', 'first_line',
                  'second_line', 'city', 'state_province_region', 'postal_code', 'country']
        widgets = {'country': forms.Select(choices=[])}

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
                'email_list': self.account.billingcontactinfo.email_list,
            }

        except BillingContactInfo.DoesNotExist:
            pass

        super(EditBillingAccountInfoForm, self).__init__(data, *args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()
        fields = [
            'company_name',
            'first_name',
            'last_name',
            crispy.Field('email_list', css_class='input-xxlarge accounting-email-select2',
                         data_initial=json.dumps(self.initial.get('email_list'))),
            'phone_number'
        ]

        if is_ops_user and self.initial.get('email_list'):
            fields.insert(4, crispy.Div(
                crispy.Div(
                    css_class='col-sm-3 col-md-2'
                ),
                crispy.Div(
                    crispy.HTML(", ".join(self.initial.get('email_list'))),
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
                crispy.Field('country', css_class="input-large accounting-country-select2",
                             data_country_code=self.current_country or '',
                             data_country_name=COUNTRIES.get(self.current_country, '')),
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
        return self.data.getlist('email_list')

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

    def __init__(self, account, domain, creating_user, plan_version, current_subscription, data=None,
                 *args, **kwargs):
        self.plan_version = plan_version
        self.current_subscription = current_subscription
        super(ConfirmNewSubscriptionForm, self).__init__(account, domain, creating_user, data=data,
                                                         *args, **kwargs)

        self.fields['plan_edition'].initial = self.plan_version.plan.edition

        from corehq.apps.domain.views.accounting import DomainSubscriptionView
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            'plan_edition',
            crispy.Fieldset(
                _("Basic Information"),
                'company_name',
                'first_name',
                'last_name',
                crispy.Field('email_list', css_class='input-xxlarge accounting-email-select2',
                             data_initial=json.dumps(self.initial.get('email_list'))),
                'phone_number',
            ),
            crispy.Fieldset(
                _("Mailing Address"),
                'first_line',
                'second_line',
                'city',
                'state_province_region',
                'postal_code',
                crispy.Field('country', css_class="input-large accounting-country-select2",
                             data_country_code=self.current_country or '',
                             data_country_name=COUNTRIES.get(self.current_country, ''))
            ),
            hqcrispy.FormActions(
                hqcrispy.LinkButton(_("Cancel"),
                                    reverse(DomainSubscriptionView.urlname,
                                            args=[self.domain]),
                                    css_class="btn btn-default"),
                StrictButton(_("Subscribe to Plan"),
                             type="submit",
                             id='btn-subscribe-to-plan',
                             css_class='btn btn-primary disable-on-submit-no-spinner '
                                       'add-spinner-on-click'),
            ),
            crispy.Hidden(name="downgrade_email_note", value="", id="downgrade-email-note"),
            crispy.Hidden(name="old_plan", value=current_subscription.plan_version.plan.edition),
            crispy.Hidden(name="new_plan", value=plan_version.plan.edition)
        )

    def save(self, commit=True):
        try:
            with transaction.atomic():
                account_save_success = super(ConfirmNewSubscriptionForm, self).save()
                if not account_save_success:
                    return False

                cancel_future_subscriptions(self.domain, datetime.date.today(), self.creating_user)
                if self.current_subscription is not None:
                    if self.is_same_edition():
                        self.current_subscription.update_subscription(
                            date_start=self.current_subscription.date_start,
                            date_end=None
                        )
                    elif self.is_downgrade_from_paid_plan() and \
                            self.current_subscription.is_below_minimum_subscription:
                        self.current_subscription.update_subscription(
                            date_start=self.current_subscription.date_start,
                            date_end=self.current_subscription.date_start + datetime.timedelta(days=30)
                        )
                        Subscription.new_domain_subscription(
                            account=self.account,
                            domain=self.domain,
                            plan_version=self.plan_version,
                            date_start=self.current_subscription.date_start + datetime.timedelta(days=30),
                            web_user=self.creating_user,
                            adjustment_method=SubscriptionAdjustmentMethod.USER,
                            service_type=SubscriptionType.PRODUCT,
                            pro_bono_status=ProBonoStatus.NO,
                            funding_source=FundingSource.CLIENT,
                        )
                    else:
                        self.current_subscription.change_plan(
                            self.plan_version,
                            web_user=self.creating_user,
                            adjustment_method=SubscriptionAdjustmentMethod.USER,
                            service_type=SubscriptionType.PRODUCT,
                            pro_bono_status=ProBonoStatus.NO,
                            do_not_invoice=False,
                            no_invoice_reason='',
                        )
                else:
                    Subscription.new_domain_subscription(
                        self.account, self.domain, self.plan_version,
                        web_user=self.creating_user,
                        adjustment_method=SubscriptionAdjustmentMethod.USER,
                        service_type=SubscriptionType.PRODUCT,
                        pro_bono_status=ProBonoStatus.NO,
                        funding_source=FundingSource.CLIENT,
                    )
                return True
        except Exception as e:
            log_accounting_error(
                "There was an error subscribing the domain '%s' to plan '%s'. Message: %s "
                % (self.domain, self.plan_version.plan.name, str(e)),
                show_stack_trace=True,
            )
            return False

    def is_same_edition(self):
        return self.current_subscription.plan_version.plan.edition == self.plan_version.plan.edition

    def is_downgrade_from_paid_plan(self):
        if self.current_subscription is None:
            return False
        elif self.current_subscription.is_trial:
            return False
        else:
            return is_downgrade(
                current_edition=self.current_subscription.plan_version.plan.edition,
                next_edition=self.plan_version.plan.edition
            )


class ConfirmSubscriptionRenewalForm(EditBillingAccountInfoForm):
    plan_edition = forms.CharField(
        widget=forms.HiddenInput,
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

        from corehq.apps.domain.views.accounting import DomainSubscriptionView
        self.helper.layout = crispy.Layout(
            'plan_edition',
            crispy.Fieldset(
                _("Basic Information"),
                'company_name',
                'first_name',
                'last_name',
                crispy.Field('email_list', css_class='input-xxlarge accounting-email-select2',
                             data_initial=json.dumps(self.initial.get('email_list'))),
                'phone_number',
            ),
            crispy.Fieldset(
                _("Mailing Address"),
                'first_line',
                'second_line',
                'city',
                'state_province_region',
                'postal_code',
                crispy.Field('country', css_class="input-large accounting-country-select2",
                             data_country_code=self.current_country or '',
                             data_country_name=COUNTRIES.get(self.current_country, ''))
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
                    css_class='btn btn-primary',
                ),
            ),
        )

    def save(self, commit=True):
        try:
            with transaction.atomic():
                account_save_success = super(ConfirmSubscriptionRenewalForm, self).save()
                if not account_save_success:
                    return False

                cancel_future_subscriptions(self.domain, self.current_subscription.date_start, self.creating_user)
                self.current_subscription.renew_subscription(
                    web_user=self.creating_user,
                    adjustment_method=SubscriptionAdjustmentMethod.USER,
                    service_type=SubscriptionType.PRODUCT,
                    pro_bono_status=ProBonoStatus.NO,
                    funding_source=FundingSource.CLIENT,
                    new_version=self.renewed_version,
                )
                return True
        except SubscriptionRenewalError as e:
            log_accounting_error(
                "Subscription for %(domain)s failed to renew due to: %(error)s." % {
                    'domain': self.domain,
                    'error': e,
                }
            )
            return False


class ProBonoForm(forms.Form):
    contact_email = MultiCharField(label=gettext_lazy("Email To"), widget=forms.Select(choices=[]))
    organization = forms.CharField(label=gettext_lazy("Organization"))
    project_overview = forms.CharField(
        widget=forms.Textarea(attrs={"class": "vertical-resize"}), label="Project overview"
    )
    airtime_expense = forms.CharField(label=gettext_lazy("Estimated annual expenditures on airtime:"))
    device_expense = forms.CharField(label=gettext_lazy("Estimated annual expenditures on devices:"))
    pay_only_features_needed = forms.CharField(
        widget=forms.Textarea(attrs={"class": "vertical-resize"}), label="Pay only features needed"
    )
    duration_of_project = forms.CharField(help_text=gettext_lazy(
        "We grant pro-bono subscriptions to match the duration of your "
        "project, up to a maximum of 12 months at a time (at which point "
        "you need to reapply)."
    ))
    domain = forms.CharField(label=gettext_lazy("Project Space"))
    dimagi_contact = forms.CharField(
        help_text=gettext_lazy("If you have already been in touch with someone from "
                    "Dimagi, please list their name."),
        required=False)
    num_expected_users = forms.CharField(label=gettext_lazy("Number of expected users"))

    def __init__(self, use_domain_field, *args, **kwargs):
        super(ProBonoForm, self).__init__(*args, **kwargs)
        if not use_domain_field:
            self.fields['domain'].required = False
        self.helper = hqcrispy.HQFormHelper()
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
                'airtime_expense',
                'device_expense',
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

    def clean_contact_email(self):
        if 'contact_email' in self.cleaned_data:
            copy = self.data.copy()
            self.data = copy
            copy.update({'contact_email': ", ".join(self.data.getlist('contact_email'))})
            return self.data.get('contact_email')

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
                          "Contact: %s" % self.cleaned_data['contact_email'])


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
                name=get_account_name_from_default_name(self.account_name),
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
        return Subscription.get_active_subscription_by_domain(self.domain)

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
                    gettext_noop('Update'),
                    css_class='disable-on-submit',
                ),
            ),
        )


class DimagiOnlyEnterpriseForm(InternalSubscriptionManagementForm):
    slug = 'dimagi_only_enterprise'
    subscription_type = gettext_noop('Test or Demo Project')

    def __init__(self, domain, web_user, *args, **kwargs):
        super(DimagiOnlyEnterpriseForm, self).__init__(domain, web_user, *args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.HTML('<div class="alert alert-info">' + gettext_noop(
                '<i class="fa fa-info-circle"></i> You will have access to all '
                'features for free as soon as you hit "Update".  Please make '
                'sure this is an internal Dimagi test space, not in use by a '
                'partner.<br>Test projects belong to Dimagi and are not subject to '
                'Dimagi\'s external terms of service.'
            ) + '</div>'),
            *self.form_actions
        )

    @transaction.atomic
    def process_subscription_management(self):
        enterprise_plan_version = DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.ENTERPRISE)
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
            'no_invoice_reason': '',
            'service_type': SubscriptionType.INTERNAL,
        })
        return fields

    @property
    def account_name(self):
        return "Dimagi Internal Test Account for Project %s" % self.domain


class AdvancedExtendedTrialForm(InternalSubscriptionManagementForm):
    slug = 'advanced_extended_trial'
    subscription_type = gettext_noop('Extended Trial')

    organization_name = forms.CharField(
        label=gettext_noop('Organization Name'),
        max_length=BillingAccount._meta.get_field('name').max_length,
    )

    emails = forms.CharField(
        label=gettext_noop('Partner Contact Emails'),
    )

    trial_length = forms.ChoiceField(
        choices=[(days, "%d days" % days) for days in [15, 30, 60, 90]],
        label="Trial Length",
    )

    def __init__(self, domain, web_user, *args, **kwargs):
        super(AdvancedExtendedTrialForm, self).__init__(domain, web_user, *args, **kwargs)

        self.fields['organization_name'].initial = self.autocomplete_account_name
        self.fields['emails'].initial = self.current_contact_emails

        self.helper = hqcrispy.HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Field('organization_name'),
            crispy.Field('emails', css_class='input-xxlarge'),
            crispy.Field('trial_length', data_bind='value: trialLength'),
            crispy.Div(
                crispy.Div(
                    crispy.HTML(_(
                        '<p><i class="fa fa-info-circle"></i> The trial will begin as soon '
                        'as you hit "Update" and end on <span data-bind="text: end_date"></span>.  '
                        'On <span data-bind="text: end_date"></span> '
                        'the project space will be automatically paused.</p>'
                    )),
                    css_class='col-sm-offset-3 col-md-offset-2'
                ),
                css_class='form-group'
            ),
            *self.form_actions
        )

    @transaction.atomic
    def process_subscription_management(self):
        advanced_trial_plan_version = DefaultProductPlan.get_default_plan_version(
            edition=SoftwarePlanEdition.ADVANCED, is_trial=True,
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
            'no_invoice_reason': '',
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
    subscription_type = gettext_noop('Contracted Partner')

    software_plan_edition = forms.ChoiceField(
        choices=(
            (SoftwarePlanEdition.STANDARD, SoftwarePlanEdition.STANDARD),
            (SoftwarePlanEdition.PRO, SoftwarePlanEdition.PRO),
            (SoftwarePlanEdition.ADVANCED, SoftwarePlanEdition.ADVANCED),
        ),
        label=gettext_noop('Software Plan'),
    )

    fogbugz_client_name = forms.CharField(
        label=gettext_noop('Fogbugz Client Name'),
        max_length=BillingAccount._meta.get_field('name').max_length,
    )

    emails = forms.CharField(
        help_text=gettext_noop(
            'This is who will receive invoices if the Client exceeds the user '
            'or SMS limits in their plan.'
        ),
        label=gettext_noop('Partner Contact Emails'),
    )

    start_date = forms.DateField(
        help_text=gettext_noop('Date the project needs access to features.'),
        label=gettext_noop('Start Date'),
    )

    end_date = forms.DateField(
        help_text=gettext_noop(
            'Specify the End Date based on the Start Date plus number of '
            'months of software plan in the contract with the Client.'
        ),
        label=gettext_noop('End Date'),
    )

    sms_credits = forms.DecimalField(
        initial=0,
        label=gettext_noop('SMS Credits'),
    )

    user_credits = forms.IntegerField(
        initial=0,
        label=gettext_noop('User Credits'),
    )

    def __init__(self, domain, web_user, *args, **kwargs):
        super(ContractedPartnerForm, self).__init__(domain, web_user, *args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()
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
                              'subscription in CommCare HQ to one of our '
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
        new_plan_version = DefaultProductPlan.get_default_plan_version(
            edition=self.cleaned_data['software_plan_edition'],
            is_report_builder_enabled=True,
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
            'no_invoice_reason': '',
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
            ('', gettext_noop('Select a subscription type...'))
        ] + [
            (form.slug, form.subscription_type)
            for form in INTERNAL_SUBSCRIPTION_MANAGEMENT_FORMS
        ],
        label=gettext_noop('Subscription Type'),
        required=False,
    )

    def __init__(self, defaults=None, disable_input=False, **kwargs):
        defaults = defaults or {}
        super(SelectSubscriptionTypeForm, self).__init__(defaults, **kwargs)

        self.helper = hqcrispy.HQFormHelper()
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


class ManageReleasesByLocationForm(forms.Form):
    app_id = forms.ChoiceField(label=gettext_lazy("Application"), choices=(), required=False)
    location_id = forms.CharField(label=gettext_lazy("Location"), widget=Select(choices=[]), required=False)
    version = forms.IntegerField(label=gettext_lazy('Version'), required=False, widget=Select(choices=[]))
    status = forms.ChoiceField(label=gettext_lazy("Status"),
                               choices=(
                                   ('', gettext_lazy('Select Status')),
                                   ('active', gettext_lazy('Active')),
                                   ('inactive', gettext_lazy('Inactive'))),
                               required=False,
                               help_text=gettext_lazy("Applicable for search only"))

    def __init__(self, request, domain, *args, **kwargs):
        self.domain = domain
        super(ManageReleasesByLocationForm, self).__init__(*args, **kwargs)
        self.fields['app_id'].choices = self.app_id_choices()
        if request.GET.get('app_id'):
            self.fields['app_id'].initial = request.GET.get('app_id')
        if request.GET.get('status'):
            self.fields['status'].initial = request.GET.get('status')
        self.helper = HQFormHelper()
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            crispy.Field('app_id', id='app-id-search-select', css_class="hqwebapp-select2"),
            crispy.Field('location_id', id='location_search_select'),
            crispy.Field('version', id='version-input'),
            crispy.Field('status', id='status-input'),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    crispy.Button('search', gettext_lazy("Search"), data_bind="click: search"),
                    crispy.Button('clear', gettext_lazy("Clear"), data_bind="click: clear"),
                    Submit('submit', gettext_lazy("Add New Restriction"))
                )
            )
        )

    def app_id_choices(self):
        choices = [(None, _('Select Application'))]
        for app in get_brief_apps_in_domain(self.domain):
            choices.append((app.id, app.name))
        return choices

    @cached_property
    def version_build_id(self):
        app_id = self.cleaned_data['app_id']
        version = self.cleaned_data['version']
        return get_version_build_id(self.domain, app_id, version)

    def clean_app_id(self):
        if not self.cleaned_data.get('app_id'):
            self.add_error('app_id', _("Please select application"))
        return self.cleaned_data.get('app_id')

    def clean_location_id(self):
        if not self.cleaned_data.get('location_id'):
            self.add_error('location_id', _("Please select location"))
        return self.cleaned_data.get('location_id')

    def clean_version(self):
        if not self.cleaned_data.get('version'):
            self.add_error('version', _("Please select version"))
        return self.cleaned_data.get('version')

    def clean(self):
        app_id = self.cleaned_data.get('app_id')
        version = self.cleaned_data.get('version')
        if app_id and version:
            try:
                self.version_build_id
            except BuildNotFoundException as e:
                self.add_error('version', e)

    def save(self):
        location_id = self.cleaned_data['location_id']
        version = self.cleaned_data['version']
        app_id = self.cleaned_data['app_id']
        try:
            AppReleaseByLocation.update_status(self.domain, app_id, self.version_build_id, location_id,
                                               version, active=True)
        except ValidationError as e:
            return False, ','.join(e.messages)
        return True, None


class BaseManageReleasesByAppProfileForm(forms.Form):
    app_id = forms.ChoiceField(label=gettext_lazy("Application"), choices=(), required=True)
    version = forms.IntegerField(label=gettext_lazy('Version'), required=False, widget=Select(choices=[]))

    def __init__(self, request, domain, *args, **kwargs):
        self.request = request
        self.domain = domain
        super(BaseManageReleasesByAppProfileForm, self).__init__(*args, **kwargs)
        self.fields['app_id'].choices = self.app_id_choices()
        self.helper = HQFormHelper()
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                "",
                *self.form_fields()
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    *self._buttons()
                )
            )
        )

    def app_id_choices(self):
        choices = [(None, _('Select Application'))]
        for app in get_brief_apps_in_domain(self.domain):
            choices.append((app.id, app.name))
        return choices

    def form_fields(self):
        return [
            crispy.Field('app_id', css_class="hqwebapp-select2 app-id-search-select"),
            crispy.Field('version', css_class='version-input'),
        ]

    @staticmethod
    def _buttons():
        raise NotImplementedError


class SearchManageReleasesByAppProfileForm(BaseManageReleasesByAppProfileForm):
    app_build_profile_id = forms.ChoiceField(label=gettext_lazy("Build Profile"), choices=(),
                                             required=False)
    status = forms.ChoiceField(label=gettext_lazy("Status"),
                               choices=(
                                   ('', gettext_lazy('Select Status')),
                                   ('active', gettext_lazy('Active')),
                                   ('inactive', gettext_lazy('Inactive'))),
                               required=False)

    def __init__(self, request, domain, *args, **kwargs):
        super(SearchManageReleasesByAppProfileForm, self).__init__(request, domain, *args, **kwargs)
        if request.GET.get('app_id'):
            self.fields['app_id'].initial = request.GET.get('app_id')
        if request.GET.get('status'):
            self.fields['status'].initial = request.GET.get('status')

    def form_fields(self):
        form_fields = super(SearchManageReleasesByAppProfileForm, self).form_fields()
        form_fields.extend([
            crispy.Field('app_build_profile_id', css_class="hqwebapp-select2 app-build-profile-id-select"),
            crispy.Field('status', id='status-input')
        ])
        return form_fields

    @staticmethod
    def _buttons():
        return [
            crispy.Button('search', gettext_lazy("Search"), data_bind="click: search",
                          css_class='btn-primary'),
            crispy.Button('clear', gettext_lazy("Clear"), data_bind="click: clear"),
        ]


class CreateManageReleasesByAppProfileForm(BaseManageReleasesByAppProfileForm):
    build_profile_id = forms.CharField(label=gettext_lazy('Build Profile'),
                                       required=True, widget=SelectMultiple(choices=[]),)

    def save(self):
        success_messages = []
        error_messages = []
        for build_profile_id in self.cleaned_data['build_profile_id']:
            try:
                LatestEnabledBuildProfiles.update_status(self.build, build_profile_id,
                                                         active=True)
                success_messages.append(_('Restriction for profile {profile} set successfully.').format(
                    profile=self.build.build_profiles[build_profile_id]['name'],
                ))
            except ValidationError as e:
                error_messages.append(_('Restriction for profile {profile} failed: {message}').format(
                    profile=self.build.build_profiles[build_profile_id]['name'],
                    message=', '.join(e.messages)
                ))
        return error_messages, success_messages

    @cached_property
    def build(self):
        return get_app(self.domain, self.version_build_id)

    @cached_property
    def version_build_id(self):
        app_id = self.cleaned_data['app_id']
        version = self.cleaned_data['version']
        return get_version_build_id(self.domain, app_id, version)

    def form_fields(self):
        form_fields = super(CreateManageReleasesByAppProfileForm, self).form_fields()
        form_fields.extend([
            crispy.Field('build_profile_id', id='build-profile-id-input')
        ])
        return form_fields

    @staticmethod
    def _buttons():
        return [Submit('submit', gettext_lazy("Add New Restriction"), css_class='btn-primary')]

    def clean(self):
        if self.cleaned_data.get('version'):
            try:
                self.version_build_id
            except BuildNotFoundException as e:
                self.add_error('version', e)

    def clean_build_profile_id(self):
        return self.data.getlist('build_profile_id')

    def clean_version(self):
        # ensure value is present for a post request
        if not self.cleaned_data.get('version'):
            self.add_error('version', _("Please select version"))
        return self.cleaned_data.get('version')


class DomainAlertForm(forms.Form):
    text = CharField(
        label="Text",
        widget=forms.Textarea,
        required=True,
    )
    start_time = DateTimeField(
        label="Start Time",
        widget=DatetimeLocalWidget,
        required=False
    )
    end_time = DateTimeField(
        label="End Time",
        widget=DatetimeLocalWidget,
        required=False
    )

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)

        datetime_local_widget_helptext = _("Using project's timezone: {}").format(
            request.project.default_timezone
        )
        self.fields['start_time'].help_text = datetime_local_widget_helptext
        self.fields['end_time'].help_text = datetime_local_widget_helptext

        self.helper = hqcrispy.HQFormHelper(self)
        self.helper.layout.append(
            hqcrispy.FormActions(
                StrictButton(
                    _('Save'),
                    type='submit',
                    css_class='btn-primary disable-on-submit'
                )
            )
        )
